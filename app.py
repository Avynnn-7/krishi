import hmac
import json
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

import click
import truststore
from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_babel import Babel, get_locale
from pydantic import ValidationError
from werkzeug.exceptions import HTTPException

from bot.alerts import dispatch_alerts, run_scheduler
from bot.parser import decipher_voice_utterance
from bot.state_machine import handle_message, quick_options_for_state, resume_prompt, session_key
from bot.webhook import webhook_bp
from engine.irrigation import load_water_data, plan_irrigation
from engine.models import BLOCKS, TEXTURES, AdvisoryInput, Crop, Soil
from engine.optimizer import OptimizationError
from engine.service import (
    build_advisory,
    build_autofill,
    load_blocks,
    load_catalog,
    load_soil_baselines,
    resolve_soil_profile,
)
from engine.simulator import Scenario, compare_scenarios
from engine.soil_card import interpret_soil
from engine.stcr import load_profiles
from engine.timing import IST
from engine.weather import resolve_location
from exports import advisory_pdf, calendar_export
from storage import (
    connect,
    get_report,
    initialize,
    list_village_soil,
    save_report,
    save_village_soil,
)

ROOT = Path(__file__).resolve().parent


def create_app(test_config: dict | None = None) -> Flask:
    load_dotenv(ROOT / ".env")
    # Trust the operating-system certificate store (campus/institutional networks add their own CAs).
    truststore.inject_into_ssl()
    app = Flask(__name__)
    instance = ROOT / "instance"
    instance.mkdir(exist_ok=True)
    secret = os.getenv("SECRET_KEY")
    if not secret and not (test_config and test_config.get("SECRET_KEY")):
        secret_file = instance / "secret.key"
        try:
            with open(secret_file, "x", opener=lambda p, flags: os.open(p, flags, 0o600)) as file:
                file.write(secrets.token_hex(32))
        except FileExistsError:
            pass
        secret = secret_file.read_text().strip()
    app.config.update(
        SECRET_KEY=secret,
        DATABASE_PATH=os.getenv("DATABASE_PATH", str(instance / "jalkhadd.db")),
        DATA_DIR=ROOT / "data",
        PUBLIC_BASE_URL=os.getenv("PUBLIC_BASE_URL", "http://localhost:5000").rstrip("/"),
        WEATHER_ENABLED=os.getenv("WEATHER_ENABLED", "true").lower() == "true",
        RATE_LIMIT_PER_MINUTE=int(os.getenv("RATE_LIMIT_PER_MINUTE", "40")),
        TRUST_PROXY=os.getenv("TRUST_PROXY", "false").lower() == "true",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        MAX_CONTENT_LENGTH=65536,
        PERMANENT_SESSION_LIFETIME=timedelta(days=7),
        BABEL_DEFAULT_LOCALE="en",
        BABEL_SUPPORTED_LOCALES=["en", "hi"],
    )
    for name in (
        "META_VERIFY_TOKEN",
        "META_APP_SECRET",
        "META_ACCESS_TOKEN",
        "META_PHONE_NUMBER_ID",
        "META_ALERT_TEMPLATE",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_WEBHOOK_URL",
    ):
        app.config[name] = os.getenv(name, "")
    app.config["META_GRAPH_VERSION"] = os.getenv("META_GRAPH_VERSION", "v23.0")
    app.config["META_ALERT_LANGUAGE"] = os.getenv("META_ALERT_LANGUAGE", "hi")
    if test_config:
        app.config.update(test_config)
    initialize(app.config["DATABASE_PATH"])
    # Fail at startup on malformed reference data, not midway through a farmer conversation.
    load_catalog(app.config["DATA_DIR"])
    load_profiles(app.config["DATA_DIR"])
    load_water_data(app.config["DATA_DIR"])
    Babel(app, locale_selector=lambda: session.get("lang", "en"))
    app.register_blueprint(webhook_bp)
    if app.config["TRUST_PROXY"]:
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    hits: dict[str, deque] = defaultdict(deque)
    hits_lock = threading.Lock()

    def rate_limited() -> bool:
        limit = app.config["RATE_LIMIT_PER_MINUTE"]
        if not limit:
            return False
        now = time.monotonic()
        with hits_lock:
            bucket = hits[request.remote_addr or "unknown"]
            while bucket and now - bucket[0] > 60:
                bucket.popleft()
            if len(bucket) >= limit:
                return True
            bucket.append(now)
            if len(hits) > 10000:
                for key in [k for k, v in hits.items() if not v or now - v[-1] > 60]:
                    del hits[key]
        return False

    @app.before_request
    def protect_request():
        if request.args.get("lang") in {"en", "hi"}:
            session["lang"] = request.args["lang"]
        session.setdefault("csrf", secrets.token_urlsafe(24))
        if request.method == "POST" and rate_limited():
            abort(429, "Too many requests. Please wait a minute and try again.")
        if request.method in {"POST", "DELETE", "PUT", "PATCH"} and request.blueprint != "webhook":
            token = request.headers.get("X-CSRF-Token", "") or request.form.get("csrf", "")
            if not hmac.compare_digest(session["csrf"], token):
                abort(400, "Session validation failed. Reload the page and try again.")

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; font-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        )
        if not request.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.context_processor
    def template_context():
        return {
            "locale": str(get_locale()),
            "csrf": session["csrf"],
            "t": lambda en, hi: hi if str(get_locale()) == "hi" else en,
            "blocks": BLOCKS,
            "block_info": load_blocks(app.config["DATA_DIR"]),
            "crops": list(Crop),
            "textures": TEXTURES,
            "lang_url": lang_url,
            "today": datetime.now(IST).date().isoformat(),
        }

    def lang_url(code: str) -> str:
        args = request.args.to_dict()
        args["lang"] = code
        if request.endpoint and request.endpoint != "static" and request.method == "GET":
            try:
                return url_for(request.endpoint, **(request.view_args or {}), **args)
            except Exception:  # noqa: BLE001 - fall back to a plain query switch
                pass
        return f"?lang={code}"

    @app.errorhandler(HTTPException)
    def http_error(exc):
        if request.path.startswith(("/api/", "/webhook/")):
            return jsonify(error=exc.description), exc.code
        return render_template("error.html", error=exc.description, code=exc.code), exc.code

    @app.errorhandler(OptimizationError)
    def optimization_error(exc):
        app.logger.error("Optimizer failed: %s", exc)
        if request.path.startswith(("/api/", "/webhook/")):
            return jsonify(error="Optimizer unavailable. Please try again."), 503
        return render_template("error.html", error=str(exc), code=503), 503

    @app.get("/")
    def index():
        return render_template("index.html")
    @app.get("/dashboard")
    def dashboard():
        return render_template("dashboard.html")    

    @app.route("/advisory", methods=["GET", "POST"])
    def advisory():
        error = None
        if request.method == "POST":
            try:
                with connect(app.config["DATABASE_PATH"]) as db:
                    raw_inputs = form_inputs(request.form, app.config["DATA_DIR"], db)
                    inputs = AdvisoryInput.model_validate(raw_inputs)
                    report = save_report(
                        db,
                        build_advisory(
                            inputs, app.config["DATA_DIR"], app.config["WEATHER_ENABLED"]
                        ),
                    )
                remember(report["id"])
                return redirect(url_for("results", report_id=report["id"]))
            except (ValueError, ValidationError) as exc:
                error = validation_message(exc)
        values = request.form
        if request.method == "GET" and request.args.get("from"):
            with connect(app.config["DATABASE_PATH"]) as db:
                source = get_report(db, request.args["from"])
            if source is None:
                abort(404, "Report to edit was not found.")
            values = flatten_inputs(source["inputs"])
        products, _ = load_catalog(app.config["DATA_DIR"])
        water, _ = load_water_data(app.config["DATA_DIR"])
        return render_template(
            "advisory_form.html",
            error=error,
            values=values,
            profiles=load_profiles(app.config["DATA_DIR"]),
            products=products,
            methods=water["methods"],
        ), 422 if error else 200

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        csp = (
            "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; "
            "font-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        )
        if request.path == "/dashboard":
            # The dashboard sets bar widths/heights with inline style attributes and loads Google Fonts.
            csp = (
                "default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "script-src 'self'; img-src 'self' data:; font-src 'self' https://fonts.gstatic.com; "
                "connect-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
            )
        response.headers["Content-Security-Policy"] = csp
        if not request.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/soil-card")
    def soil_card():
        values, report, error = request.args, None, None
        if request.args.get("N"):
            try:
                soil = Soil.model_validate(soil_fields(request.args, prefix=""))
                area = float(request.args.get("area_ha") or 1)
                if not 0 < area <= 100:
                    raise ValueError("Area must be between 0 and 100 ha.")
                report = interpret_soil(soil, app.config["DATA_DIR"], area)
            except (ValueError, ValidationError) as exc:
                error = validation_message(exc)
        return render_template("soil_card.html", values=values, report=report, error=error), (
            422 if error else 200
        )

    @app.get("/water")
    def water_planner():
        water, _ = load_water_data(app.config["DATA_DIR"])
        values, plan, error = request.args, None, None
        if request.args.get("crop"):
            try:
                args = request.args
                crop = Crop(args["crop"])
                texture = args.get("texture", "loam")
                if texture not in TEXTURES:
                    raise ValueError("Unknown soil texture.")
                area = float(args.get("area") or 1)
                unit_m2 = {"ha": 10000, "acre": 4046.8564224}.get(args.get("area_unit", "ha"))
                if unit_m2 is None:
                    unit_m2 = float(args.get("bigha_m2") or 0)
                    if not 100 <= unit_m2 <= 10000:
                        raise ValueError("Enter local square metres per bigha (100–10,000).")
                area_ha = area * unit_m2 / 10000
                if not 0 < area_ha <= 100:
                    raise ValueError("Area must be greater than 0 and at most 100 ha.")
                flow = optional_float(args.get("flow_lps"), 0.01, 500, "Flow")
                turn = optional_float(args.get("turn_hours"), 0.01, 72, "Turn duration")
                limit = optional_float(args.get("max_irrigations"), 0, 30, "Available irrigations")
                sowing = date.fromisoformat(args.get("sowing_date", ""))
                if not 1900 <= sowing.year <= 2100:
                    raise ValueError("Sowing date must be between 1900 and 2100.")
                plan = plan_irrigation(
                    crop.value,
                    sowing,
                    texture,
                    area_ha,
                    app.config["DATA_DIR"],
                    args.get("method") or None,
                    flow,
                    turn,
                    int(limit) if limit is not None else None,
                )
            except (ValueError, KeyError) as exc:
                error = str(exc) or "Check the inputs."
        return render_template(
            "water.html",
            values=values,
            plan=plan,
            error=error,
            methods=water["methods"],
            crop_water=water["crops"],
        ), 422 if error else 200

    def report_or_404(report_id: str) -> dict:
        with connect(app.config["DATABASE_PATH"]) as db:
            report = get_report(db, report_id)
        if report is None:
            abort(404, "Report not found or deleted.")
        return report

    @app.get("/results/<report_id>")
    def results(report_id: str):
        return render_template("results.html", report=report_or_404(report_id))

    @app.get("/results/<report_id>/pdf")
    def pdf(report_id: str):
        content = advisory_pdf(
            report_or_404(report_id),
            ROOT / "static/fonts/JalKhaddSans-Regular.ttf",
            str(get_locale()) == "hi",
        )
        return send_file(
            BytesIO(content),
            mimetype="application/pdf",
            as_attachment=True,
            download_name="jal-khadd-advisory.pdf",
        )

    @app.get("/results/<report_id>/calendar.ics")
    def calendar(report_id: str):
        return app.response_class(
            calendar_export(report_or_404(report_id)),
            mimetype="text/calendar",
            headers={"Content-Disposition": "attachment; filename=jal-khadd-calendar.ics"},
        )

    @app.get("/results/<report_id>/json")
    def json_report(report_id: str):
        return jsonify(report_or_404(report_id))

    @app.get("/history")
    def history():
        with connect(app.config["DATABASE_PATH"]) as db:
            reports = [
                report
                for id_ in reversed(session.get("reports", []))
                if (report := get_report(db, id_))
            ]
        return render_template("history.html", reports=reports)

    @app.post("/results/<report_id>/delete")
    def delete_report(report_id: str):
        if report_id not in session.get("reports", []):
            abort(403, "Only reports created in this browser can be deleted here.")
        with connect(app.config["DATABASE_PATH"]) as db:
            db.execute("DELETE FROM recommendations WHERE id=?", (report_id,))
        session["reports"] = [id_ for id_ in session["reports"] if id_ != report_id]
        return redirect(url_for("history"))

    @app.route("/simulator", methods=["GET", "POST"])
    def simulator():
        error = None
        values = Scenario().model_dump()
        output = compare_scenarios(Scenario())
        if request.method == "POST":
            try:
                raw = {key: value for key, value in request.form.items() if key != "csrf"}
                scenario = Scenario.model_validate(raw)
                values, output = scenario.model_dump(), compare_scenarios(scenario)
            except ValidationError as exc:
                error, output = validation_message(exc), None
                values.update(raw)
        return render_template(
            "simulator.html", values=values, output=output, error=error
        ), 422 if error else 200

    @app.get("/about")
    def about():
        return render_template("about.html", weather_enabled=app.config["WEATHER_ENABLED"])

    @app.get("/bot")
    def bot_demo():
        session.setdefault("bot_id", secrets.token_urlsafe(24))
        identity = "demo:" + session["bot_id"]
        with connect(app.config["DATABASE_PATH"]) as db:
            prompt = resume_prompt(
                db,
                identity,
                app.config["SECRET_KEY"],
                request.host_url.rstrip("/"),
            )
            row = db.execute(
                "SELECT payload FROM bot_sessions WHERE session_key=?",
                (session_key(identity, app.config["SECRET_KEY"]),),
            ).fetchone()
            state = json.loads(row["payload"]) if row else {"step": "BLOCK", "inputs": {}}
            options = quick_options_for_state(state, app.config["DATA_DIR"])
            autofill = build_autofill(
                app.config["DATA_DIR"],
                db=db,
                block=state.get("inputs", {}).get("block", "Roorkee"),
                village=state.get("inputs", {}).get("village", "Dhandera"),
                crop=state.get("inputs", {}).get("crop", "wheat"),
                weather_enabled=app.config["WEATHER_ENABLED"],
            )
        return render_template("bot.html", prompt=prompt, options=options, autofill=autofill)

    @app.post("/api/bot")
    def bot_message():
        payload = request.get_json()
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("text"), str)
            or not 1 <= len(payload["text"].strip()) <= 2000
        ):
            abort(422, "Send a text message of 1–2000 characters.")
        session.setdefault("bot_id", secrets.token_urlsafe(24))
        with connect(app.config["DATABASE_PATH"]) as db:
            db.execute("BEGIN IMMEDIATE")
            reply = handle_message(
                db,
                "demo:" + session["bot_id"],
                payload["text"],
                app.config["SECRET_KEY"],
                app.config["DATA_DIR"],
                request.host_url.rstrip("/"),
                app.config["WEATHER_ENABLED"],
            )
            inputs_so_far = reply.get("inputs") or {}
            reply["autofill"] = build_autofill(
                app.config["DATA_DIR"],
                db=db,
                block=inputs_so_far.get("block", "Roorkee"),
                village=inputs_so_far.get("village", "Dhandera"),
                crop=inputs_so_far.get("crop", "wheat"),
                weather_enabled=app.config["WEATHER_ENABLED"],
            )
        return jsonify(reply)

    @app.get("/api/autofill")
    def api_autofill():
        try:
            lat = optional_float(request.args.get("lat"), -90, 90, "Latitude")
            lon = optional_float(request.args.get("lon"), -180, 180, "Longitude")
            area = optional_float(request.args.get("area"), 0.001, 10000, "Area") or 5.0
            unit = request.args.get("area_unit", "bigha")
            bigha_m2 = (
                optional_float(request.args.get("bigha_m2"), 100, 10000, "Bigha m2") or 632.29
            )
            area_ha = (
                area * 0.40468564224
                if unit == "acre"
                else area * bigha_m2 / 10000
                if unit == "bigha"
                else area
            )
            with connect(app.config["DATABASE_PATH"]) as db:
                data = build_autofill(
                    app.config["DATA_DIR"],
                    db=db,
                    block=request.args.get("block") or None,
                    village=request.args.get("village") or None,
                    lat=lat,
                    lon=lon,
                    query=request.args.get("q") or None,
                    crop=request.args.get("crop", "wheat"),
                    area_ha=area_ha,
                    weather_enabled=app.config["WEATHER_ENABLED"],
                )
            return jsonify(data)
        except ValueError as exc:
            return jsonify(error=str(exc)), 422

    @app.get("/api/geocode")
    def api_geocode():
        try:
            lat = optional_float(request.args.get("lat"), -90, 90, "Latitude")
            lon = optional_float(request.args.get("lon"), -180, 180, "Longitude")
            loc = resolve_location(
                load_blocks(app.config["DATA_DIR"]),
                block=request.args.get("block") or None,
                village=request.args.get("village") or None,
                lat=lat,
                lon=lon,
                query=request.args.get("q") or None,
                online_geocode=app.config["WEATHER_ENABLED"],
            )
            return jsonify(loc)
        except ValueError as exc:
            return jsonify(error=str(exc)), 422

    @app.post("/api/voice-decipher")
    def api_voice_decipher():
        payload = request.get_json()
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("text"), str)
            or not payload["text"].strip()
        ):
            abort(422, "Provide spoken text to decipher.")
        blocks_data = load_blocks(app.config["DATA_DIR"])
        parsed = decipher_voice_utterance(payload["text"], blocks_data)
        with connect(app.config["DATABASE_PATH"]) as db:
            autofill = build_autofill(
                app.config["DATA_DIR"],
                db=db,
                block=parsed.get("block"),
                village=parsed.get("village"),
                crop=parsed.get("crop", "wheat"),
                weather_enabled=app.config["WEATHER_ENABLED"],
            )
        return jsonify(parsed=parsed, autofill=autofill)

    @app.route("/village-soil", methods=["GET", "POST"])
    def village_soil_hub():
        error, saved_msg = None, None
        if request.method == "POST":
            try:
                records = parse_village_soil_submission(request.form)
                with connect(app.config["DATABASE_PATH"]) as db:
                    for rec in records:
                        save_village_soil(db, rec)
                saved_msg = f"Saved {len(records)} official village soil profile(s)."
            except (ValueError, ValidationError) as exc:
                error = validation_message(exc)
        with connect(app.config["DATABASE_PATH"]) as db:
            uploaded = list_village_soil(db)
        baselines = load_soil_baselines(app.config["DATA_DIR"])
        return render_template(
            "village_soil.html",
            baselines=baselines,
            uploaded=uploaded,
            error=error,
            saved_msg=saved_msg,
        ), 422 if error else 200

    @app.route("/api/village-soil", methods=["GET", "POST"])
    def api_village_soil():
        if request.method == "GET":
            with connect(app.config["DATABASE_PATH"]) as db:
                uploaded = list_village_soil(db)
            return jsonify(
                uploaded=uploaded,
                baselines=load_soil_baselines(app.config["DATA_DIR"]),
            )
        try:
            payload = request.get_json()
            if not isinstance(payload, dict):
                raise ValueError("JSON object required.")
            rec = validate_village_soil_record(payload)
            with connect(app.config["DATABASE_PATH"]) as db:
                saved = save_village_soil(db, rec)
            return jsonify(saved), 201
        except (ValueError, ValidationError) as exc:
            return jsonify(error=validation_message(exc)), 422

    @app.get("/api/config")
    def api_config():
        return jsonify(
            csrf=session["csrf"],
            blocks=BLOCKS,
            crops=[c.value for c in Crop],
            profiles=list(load_profiles(app.config["DATA_DIR"])),
        )

    @app.post("/api/advisory")
    def api_advisory():
        try:
            inputs = AdvisoryInput.model_validate(request.get_json())
            with connect(app.config["DATABASE_PATH"]) as db:
                report = save_report(
                    db,
                    build_advisory(inputs, app.config["DATA_DIR"], app.config["WEATHER_ENABLED"]),
                )
            remember(report["id"])
            return jsonify(report), 201
        except (ValueError, ValidationError) as exc:
            return jsonify(error=validation_message(exc)), 422

    @app.get("/health")
    def health():
        with connect(app.config["DATABASE_PATH"]) as db:
            db.execute("SELECT 1")
        return {"status": "ok", "mode": "prototype"}

    @app.cli.command("alerts")
    @click.option("--once", is_flag=True, help="Run one alert sweep instead of the scheduler.")
    def alerts_command(once: bool):
        """Run exactly one dedicated scheduler process (07:00 Asia/Kolkata)."""
        if once:
            click.echo(f"Alerts sent: {dispatch_alerts(app.config)}")
        else:
            run_scheduler(app.config)

    @app.cli.command("purge-data")
    @click.option("--days", default=30, type=click.IntRange(min=1))
    def purge_data(days: int):
        """Delete expired sessions, old reports and delivery receipts; keep opted-in subscriptions."""
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(days=days)).isoformat()
        with connect(app.config["DATABASE_PATH"]) as db:
            db.execute("DELETE FROM recommendations WHERE created_at < ?", (cutoff,))
            db.execute("DELETE FROM inbox WHERE created_at < ?", (cutoff,))
            db.execute("DELETE FROM bot_sessions WHERE updated_at < ?", (cutoff,))
        click.echo(
            f"Removed data older than {days} days; explicit alert consent is retained until STOP."
        )

    return app


def remember(report_id: str) -> None:
    session["reports"] = (session.get("reports", []) + [report_id])[-20:]
    session.permanent = True


def validation_message(exc: ValueError) -> str:
    if isinstance(exc, ValidationError):
        return "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
    return str(exc)


SOIL_KEYS = (
    "N",
    "P",
    "K",
    "basis",
    "ph",
    "ec",
    "organic_carbon",
    "sulphur",
    "zinc",
    "iron",
    "manganese",
    "copper",
    "boron",
)
SIMPLE_FIELDS = set(AdvisoryInput.model_fields) - {
    "soil",
    "prices",
    "unavailable",
    "current_practice",
}


def soil_fields(form, prefix: str = "soil_") -> dict:
    values = {}
    for key in SOIL_KEYS:
        raw = form.get(f"{prefix}{key}", "")
        if raw not in ("", None):
            values[key] = raw
    return values


def optional_float(raw: str | None, low: float, high: float, label: str) -> float | None:
    if raw in (None, ""):
        return None
    value = float(raw)
    if not low <= value <= high:
        raise ValueError(f"{label} must be between {low:g} and {high:g}.")
    return value


def form_inputs(form, data_dir: Path | None = None, db=None) -> dict:
    values = {key: form[key] for key in SIMPLE_FIELDS if form.get(key)}
    soil_mode = form.get("soil_mode", "none")
    if soil_mode == "card":
        values["soil"] = soil_fields(form)
        values["soil"].setdefault("basis", "elemental")
        values["soil_source"] = "card"
    elif soil_mode == "auto" and data_dir is not None:
        prof = resolve_soil_profile(
            values.get("block", "Roorkee"), values.get("village"), data_dir, db=db
        )
        values["soil"] = prof["soil"]
        values["soil_source"] = prof["tier"]
        values.setdefault("texture", prof.get("texture", "sandy-loam"))
    if data_dir is not None and not values.get("latitude") and values.get("block") in BLOCKS:
        loc = resolve_location(
            load_blocks(data_dir),
            block=values.get("block"),
            village=values.get("village"),
            online_geocode=False,
        )
        values["latitude"] = loc["latitude"]
        values["longitude"] = loc["longitude"]
    prices, practice, unavailable = {}, {}, []
    for key, raw in form.items():
        if key.startswith("price_") and raw:
            prices[key.removeprefix("price_")] = raw
        elif key.startswith("practice_") and raw and float(raw) > 0:
            practice[key.removeprefix("practice_")] = raw
        elif key.startswith("unavailable_") and raw:
            unavailable.append(key.removeprefix("unavailable_"))
    values.update(prices=prices, current_practice=practice, unavailable=unavailable)
    return values


def flatten_inputs(inputs: dict) -> dict:
    """Convert saved report inputs back into advisory form field names for editing."""
    values = {
        key: "" if value is None else str(value)
        for key, value in inputs.items()
        if key in SIMPLE_FIELDS
    }
    if inputs.get("irrigation_at"):
        values["irrigation_at"] = inputs["irrigation_at"][:16]
    if inputs.get("soil"):
        source = inputs.get("soil_source")
        values["soil_mode"] = "auto" if source in {"official_village", "block_baseline"} else "card"
        for key, value in inputs["soil"].items():
            if value is not None:
                values[f"soil_{key}"] = str(value)
    else:
        values["soil_mode"] = "none"
    for key, value in inputs.get("prices", {}).items():
        values[f"price_{key}"] = str(value)
    for key, value in inputs.get("current_practice", {}).items():
        values[f"practice_{key}"] = str(value)
    for key in inputs.get("unavailable", []):
        values[f"unavailable_{key}"] = "1"
    return values


def validate_village_soil_record(raw: dict) -> dict:
    block = str(raw.get("block", "")).strip()
    if block not in BLOCKS:
        raise ValueError("Select a valid Haridwar block.")
    village = str(raw.get("village", "")).strip()
    if not 1 <= len(village) <= 80:
        raise ValueError("Village name must be 1–80 characters.")
    texture = str(raw.get("texture", "sandy-loam")).strip()
    if texture not in TEXTURES:
        raise ValueError("Invalid soil texture.")
    soil_dict = {k: raw[k] for k in SOIL_KEYS if raw.get(k) not in ("", None)}
    soil_dict.setdefault("basis", "elemental")
    validated_soil = Soil.model_validate(soil_dict).model_dump(mode="json")
    samples = int(raw.get("samples") or 1)
    if not 1 <= samples <= 5000:
        raise ValueError("Sample count must be between 1 and 5,000.")
    source = str(
        raw.get("source")
        or "Official Village Soil Health Test (Agricultural Testing Official / KVK)"
    ).strip()[:160]
    tested_date = str(raw.get("tested_date") or datetime.now(IST).date().isoformat()).strip()[:20]
    return {
        "block": block,
        "village": village,
        "village_hi": str(raw.get("village_hi") or village).strip()[:80],
        "texture": texture,
        "samples": samples,
        "source": source,
        "tested_date": tested_date,
        **validated_soil,
    }


def parse_village_soil_submission(form) -> list[dict]:
    """Support either single-village form entry or multi-row CSV/TSV paste from official lab sheets."""
    import csv
    from io import StringIO

    csv_text = (form.get("csv_rows") or "").strip()
    if not csv_text:
        return [validate_village_soil_record(form)]
    dialect = "\t" if "\t" in csv_text.splitlines()[0] else ","
    reader = csv.DictReader(StringIO(csv_text), delimiter=dialect)
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in reader:
        clean = {str(k).strip(): str(v).strip() for k, v in row.items() if k and v is not None}
        if not clean.get("village") or not clean.get("N"):
            continue
        block = clean.get("block") or form.get("block") or "Roorkee"
        grouped[(block, clean["village"])].append(clean)
    if not grouped:
        raise ValueError(
            "CSV must include header columns: village,N,P,K (and optional block,ph,ec,organic_carbon,sulphur,zinc,iron,manganese,copper,boron)."
        )
    records = []
    numeric_cols = [k for k in SOIL_KEYS if k != "basis"]
    for (block, village), rows in grouped.items():
        averaged: dict[str, object] = {
            "block": block,
            "village": village,
            "village_hi": rows[0].get("village_hi") or village,
            "texture": rows[0].get("texture") or form.get("texture") or "sandy-loam",
            "basis": rows[0].get("basis") or "elemental",
            "samples": sum(int(r.get("samples") or 1) for r in rows),
            "source": rows[0].get("source")
            or form.get("source")
            or "Agricultural Testing Official CSV Import",
            "tested_date": rows[0].get("tested_date")
            or form.get("tested_date")
            or datetime.now(IST).date().isoformat(),
        }
        for col in numeric_cols:
            vals = [float(r[col]) for r in rows if r.get(col) not in ("", None)]
            if vals:
                averaged[col] = round(sum(vals) / len(vals), 3)
        records.append(validate_village_soil_record(averaged))
    return records


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=False)
