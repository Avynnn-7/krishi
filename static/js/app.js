"use strict";

const language = document.documentElement.lang;
const text = (en, hi) => (language === "hi" ? hi : en);
const csrf = document.querySelector('meta[name="csrf-token"]')?.content || "";
const multiForm = document.querySelector("[data-multistep]");

function startSpeechRecognition(onResult, onStatus) {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    onStatus?.(
      text(
        "Browser speech recognition unavailable here — click any 🗣️ sample voice phrase below or type.",
        "इस ब्राउज़र में सीधा माइक उपलब्ध नहीं है — नीचे दिए 🗣️ वाक्य बटन दबाएँ या लिखें।"
      ),
      true
    );
    return;
  }
  const rec = new SR();
  rec.lang = language === "hi" ? "hi-IN" : "en-IN";
  rec.interimResults = false;
  rec.maxAlternatives = 1;
  onStatus?.(text("🎤 Listening… speak now in Hindi or English", "🎤 सुन रहे हैं… हिंदी या अंग्रेज़ी में बोलें"), false);
  rec.onresult = event => {
    const transcript = event.results?.[0]?.[0]?.transcript || "";
    if (transcript) {
      onStatus?.(text(`🎤 Heard: "${transcript}"`, `🎤 सुना गया: "${transcript}"`), false);
      onResult(transcript);
    }
  };
  rec.onerror = () => {
    onStatus?.(
      text(
        "Could not hear clearly — click a 🗣️ sample voice phrase or try again.",
        "आवाज़ साफ़ नहीं आई — नीचे 🗣️ वाक्य बटन दबाएँ या फिर कोशिश करें।"
      ),
      true
    );
  };
  rec.start();
}

if (multiForm) {
  const steps = [...multiForm.querySelectorAll("[data-step]")];
  const tabs = [...multiForm.querySelectorAll(".step-nav span")];
  const previous = multiForm.querySelector("[data-previous]");
  const next = multiForm.querySelector("[data-next]");
  const submit = multiForm.querySelector("[data-submit]");
  const areaUnit = document.querySelector("#area-unit");
  const soilMode = document.querySelector("#soil-mode");
  const blockSelect = document.querySelector("#block-select");
  const villageSelect = document.querySelector("#village-select");
  const villageInput = document.querySelector("#village-input");
  const cropInput = document.querySelector("#crop");
  const areaInput = document.querySelector("#area-input");
  const budgetInput = document.querySelector("#budget-input");
  const suggestedBudgetBtn = document.querySelector("#suggested-budget-btn");
  let current = 0;

  function conditionalFields() {
    const bigha = document.querySelector("#bigha-field");
    if (bigha && areaUnit) {
      bigha.hidden = areaUnit.value !== "bigha";
      bigha.querySelectorAll("input, select").forEach(el => {
        el.disabled = bigha.hidden;
      });
      const bighaM2 = document.querySelector("#bigha-m2");
      if (bighaM2) bighaM2.required = !bigha.hidden;
    }
    const soil = document.querySelector("#soil-fields");
    if (soil && soilMode) {
      soil.hidden = soilMode.value !== "card";
      soil.querySelectorAll("input, select").forEach(input => {
        input.disabled = soil.hidden;
        input.required = !soil.hidden && input.hasAttribute("data-soil-required");
      });
    }
  }

  function showStep() {
    steps.forEach((step, index) => {
      step.hidden = index !== current;
    });
    tabs.forEach((tab, index) => {
      tab.classList.toggle("active", index === current);
      if (index === current) tab.setAttribute("aria-current", "step");
      else tab.removeAttribute("aria-current");
    });
    previous.hidden = current === 0;
    next.hidden = current === steps.length - 1;
    submit.hidden = current !== steps.length - 1;
    multiForm.querySelector("[data-step-status]").textContent = `${current + 1} / ${steps.length}`;
  }

  function validStep(index) {
    const invalid = [...steps[index].querySelectorAll("input, select")].find(
      input => !input.disabled && !input.checkValidity()
    );
    if (invalid) {
      current = index;
      showStep();
      invalid.reportValidity();
      return false;
    }
    return true;
  }

  function filterVillageOptions() {
    if (!blockSelect || !villageSelect) return;
    const b = blockSelect.value;
    let firstForBlock = null;
    [...villageSelect.options].forEach(opt => {
      if (!opt.dataset.block) return;
      const match = opt.dataset.block === b;
      opt.hidden = !match;
      if (match && !firstForBlock) firstForBlock = opt;
    });
    const currentOpt = [...villageSelect.options].find(
      o => o.value && o.value.toLowerCase() === (villageInput?.value || "").trim().toLowerCase()
    );
    if (currentOpt && currentOpt.dataset.block === b) {
      villageSelect.value = currentOpt.value;
    } else if (firstForBlock && (!villageInput.value || villageSelect.dataset.autoSync === "1")) {
      villageSelect.value = firstForBlock.value;
      villageInput.value = firstForBlock.value;
    }
    villageSelect.dataset.autoSync = "1";
  }

  async function refreshAutofill(extraParams = {}) {
    const params = new URLSearchParams({
      block: blockSelect?.value || "Roorkee",
      village: villageInput?.value || "Dhandera",
      crop: cropInput?.value || "wheat",
      area: areaInput?.value || "5",
      area_unit: areaUnit?.value || "bigha",
      bigha_m2: document.querySelector("#bigha-m2")?.value || "632.29",
      ...extraParams,
    });
    try {
      const resp = await fetch(`/api/autofill?${params.toString()}`);
      if (!resp.ok) return;
      const data = await resp.json();
      if (data.location) {
        if (extraParams.lat || extraParams.q) {
          if (blockSelect) blockSelect.value = data.location.block;
          filterVillageOptions();
          if (villageInput) villageInput.value = data.location.village;
          if (villageSelect) villageSelect.value = data.location.village;
        }
        const latEl = document.querySelector("#lat");
        const lonEl = document.querySelector("#lon");
        if (latEl) latEl.value = data.location.latitude;
        if (lonEl) lonEl.value = data.location.longitude;
      }
      if (data.texture && document.querySelector("#texture-select")) {
        document.querySelector("#texture-select").value = data.texture;
      }
      if (data.soil_profile) {
        const sp = data.soil_profile;
        const s = sp.soil;
        const titleEl = document.querySelector("#af-soil-title");
        const detailEl = document.querySelector("#af-soil-detail");
        if (titleEl) {
          titleEl.textContent = `🧪 ${language === "hi" ? sp.tier_label_hi : sp.tier_label_en}`;
        }
        if (detailEl) {
          detailEl.textContent = `N ${s.N} · P ${s.P} · K ${s.K} kg/ha · pH ${s.ph ?? "—"} · OC ${s.organic_carbon ?? "—"}% · Zn ${s.zinc ?? "—"} mg/kg · S ${s.sulphur ?? "—"} mg/kg`;
        }
      }
      if (data.realtime_water) {
        const rw = data.realtime_water;
        const waterEl = document.querySelector("#af-water-detail");
        if (waterEl) {
          waterEl.textContent = `🌦️ ${language === "hi" ? rw.advice_hi : rw.advice_en}`;
        }
      }
      if (data.defaults?.suggested_budget_rs && suggestedBudgetBtn) {
        const bVal = Math.round(data.defaults.suggested_budget_rs);
        suggestedBudgetBtn.dataset.budgetPreset = String(bVal);
        suggestedBudgetBtn.textContent = text(
          `✨ Recommended: ₹${bVal.toLocaleString("en-IN")}`,
          `✨ सुझाया बजट: ₹${bVal.toLocaleString("en-IN")}`
        );
      }
    } catch {
      // Keep form usable offline
    }
  }

  async function applySpokenToForm(utterance) {
    const statusEl = document.querySelector("#form-voice-status");
    try {
      const resp = await fetch("/api/voice-decipher", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify({ text: utterance }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || "Voice parse failed");
      const p = data.parsed || {};
      if (p.block && blockSelect) {
        blockSelect.value = p.block;
        filterVillageOptions();
      }
      if (p.village && villageInput) {
        villageInput.value = p.village;
        if (villageSelect) villageSelect.value = p.village;
      }
      if (p.crop && cropInput) {
        cropInput.value = p.crop;
        cropInput.dispatchEvent(new Event("change"));
      }
      if (p.area && areaInput) areaInput.value = p.area;
      if (p.area_unit && areaUnit) {
        areaUnit.value = p.area_unit;
        conditionalFields();
      }
      if (p.budget && budgetInput) budgetInput.value = p.budget;
      await refreshAutofill();
      if (statusEl) {
        statusEl.textContent = text(
          `✅ Filled from speech: "${utterance}"`,
          `✅ आवाज़ से भर दिया गया: "${utterance}"`
        );
      }
    } catch (err) {
      if (statusEl) statusEl.textContent = err.message;
    }
  }

  blockSelect?.addEventListener("change", () => {
    filterVillageOptions();
    refreshAutofill();
  });
  villageSelect?.addEventListener("change", () => {
    if (villageSelect.value && villageInput) {
      villageInput.value = villageSelect.value;
      refreshAutofill();
    }
  });
  villageInput?.addEventListener("change", () => refreshAutofill());
  cropInput?.addEventListener("change", () => refreshAutofill());
  areaInput?.addEventListener("change", () => refreshAutofill());
  areaUnit?.addEventListener("change", () => {
    conditionalFields();
    refreshAutofill();
  });
  soilMode?.addEventListener("change", conditionalFields);

  document.querySelectorAll("[data-area-preset]").forEach(btn => {
    btn.addEventListener("click", () => {
      if (areaInput) areaInput.value = btn.dataset.areaPreset;
      if (areaUnit && btn.dataset.unitPreset) {
        areaUnit.value = btn.dataset.unitPreset;
        conditionalFields();
      }
      refreshAutofill();
    });
  });

  document.querySelectorAll("[data-budget-preset]").forEach(btn => {
    btn.addEventListener("click", () => {
      if (budgetInput) budgetInput.value = btn.dataset.budgetPreset;
    });
  });

  const waterPreset = document.querySelector("#water-source-preset");
  waterPreset?.addEventListener("change", () => {
    const opt = waterPreset.selectedOptions[0];
    if (waterPreset.value) {
      const flowEl = document.querySelector("#flow-lps");
      const hoursEl = document.querySelector("#turn-hours");
      if (flowEl) flowEl.value = waterPreset.value;
      if (hoursEl && opt?.dataset.hours) hoursEl.value = opt.dataset.hours;
    }
  });

  document.querySelector("#form-mic-btn")?.addEventListener("click", () => {
    const statusEl = document.querySelector("#form-voice-status");
    startSpeechRecognition(
      transcript => applySpokenToForm(transcript),
      msg => {
        if (statusEl) statusEl.textContent = msg;
      }
    );
  });

  document.querySelectorAll("[data-form-voice-sample]").forEach(btn => {
    btn.addEventListener("click", () => applySpokenToForm(btn.dataset.formVoiceSample));
  });

  document.querySelector("#place-search-btn")?.addEventListener("click", () => {
    const q = document.querySelector("#place-search")?.value?.trim();
    if (q) refreshAutofill({ q });
  });

  next.addEventListener("click", () => {
    if (validStep(current)) {
      current += 1;
      showStep();
      steps[current].querySelector("input, select")?.focus();
    }
  });
  previous.addEventListener("click", () => {
    current -= 1;
    showStep();
  });
  multiForm.noValidate = true;
  multiForm.addEventListener("submit", event => {
    for (let index = 0; index < steps.length; index += 1) {
      if (!validStep(index)) {
        event.preventDefault();
        return;
      }
    }
    submit.disabled = true;
    submit.textContent = text("Calculating…", "गणना जारी…");
  });

  filterVillageOptions();
  conditionalFields();
  showStep();
  refreshAutofill();
}

const chatForm = document.querySelector("#chat-form");
if (chatForm) {
  const log = document.querySelector("#chat-log");
  const input = document.querySelector("#chat-text");
  const button = chatForm.querySelector('button[type="submit"]');
  const optionsBox = document.querySelector("#chat-options");
  const voiceStatus = document.querySelector("#voice-status");

  function appendMessage(content, role, documentUrl) {
    const bubble = document.createElement("div");
    bubble.className = `chat-message ${role}`;
    const fragments = content.split(/(https?:\/\/[^\s]+)/g);
    fragments.forEach(fragment => {
      if (/^https?:\/\//.test(fragment)) {
        const url = new URL(fragment);
        if (url.origin === location.origin) {
          const link = document.createElement("a");
          link.href = url.href;
          link.textContent = text("Open report ↗", "रिपोर्ट खोलें ↗");
          bubble.append(link);
          return;
        }
      }
      bubble.append(document.createTextNode(fragment));
    });
    if (documentUrl) {
      const url = new URL(documentUrl);
      if (url.origin === location.origin) {
        const link = document.createElement("a");
        link.href = url.href;
        link.textContent = "\nPDF ↓";
        bubble.append(link);
      }
    }
    log.append(bubble);
    log.scrollTop = log.scrollHeight;
  }

  function renderBotOptions(options) {
    if (!optionsBox || !Array.isArray(options)) return;
    optionsBox.replaceChildren();
    options.forEach(opt => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "chip";
      chip.dataset.chatOption = opt.value;
      chip.textContent = opt.label;
      chip.addEventListener("click", () => sendBotMessage(opt.value));
      optionsBox.append(chip);
    });
  }

  function updateBotTelemetry(af) {
    if (!af) return;
    const locEl = document.querySelector("#tel-loc");
    const gpsEl = document.querySelector("#tel-gps");
    const tierEl = document.querySelector("#tel-soil-tier");
    const npkEl = document.querySelector("#tel-soil-npk");
    const waterEl = document.querySelector("#tel-water");
    const etEl = document.querySelector("#tel-et");
    if (locEl && af.location) {
      locEl.textContent = `${language === "hi" ? af.location.village_hi : af.location.village} (${af.location.block})`;
    }
    if (gpsEl && af.location) {
      gpsEl.textContent = `${af.location.latitude}, ${af.location.longitude} · ${af.texture}`;
    }
    if (tierEl && af.soil_profile) {
      tierEl.textContent = language === "hi" ? af.soil_profile.tier_label_hi : af.soil_profile.tier_label_en;
    }
    if (npkEl && af.soil_profile?.soil) {
      const s = af.soil_profile.soil;
      npkEl.textContent = `N ${s.N} · P ${s.P} · K ${s.K} kg/ha · pH ${s.ph} · Zn ${s.zinc}`;
    }
    if (waterEl && af.realtime_water) {
      const rw = af.realtime_water;
      waterEl.textContent = `~${rw.gross_cm} cm (${Number(rw.litres_per_bigha).toLocaleString("en-IN")} L/bigha)`;
    }
    if (etEl && af.realtime_water) {
      const rw = af.realtime_water;
      etEl.textContent = `7d ET₀ ${rw.et0_7d_mm} mm · Rain ${rw.rain_7d_mm} mm`;
    }
  }

  async function sendBotMessage(messageText) {
    const message = messageText.trim();
    if (!message) return;
    appendMessage(message, "user");
    button.disabled = true;
    input.disabled = true;
    try {
      const response = await fetch("/api/bot", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify({ text: message }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      appendMessage(data.text, "assistant", data.document);
      renderBotOptions(data.options);
      updateBotTelemetry(data.autofill);
      input.value = "";
    } catch (error) {
      appendMessage(
        text(
          "Message failed. Your reply is retained; reload if the session expired. ",
          "संदेश विफल। जवाब सुरक्षित है; सत्र समाप्त हो तो पृष्ठ पुनः खोलें। "
        ) + error.message,
        "error"
      );
    } finally {
      button.disabled = false;
      input.disabled = false;
      input.focus();
    }
  }

  chatForm.addEventListener("submit", event => {
    event.preventDefault();
    sendBotMessage(input.value);
  });

  document.querySelectorAll("[data-chat-option]").forEach(btn => {
    btn.addEventListener("click", () => sendBotMessage(btn.dataset.chatOption));
  });

  document.querySelectorAll("[data-voice-sample]").forEach(btn => {
    btn.addEventListener("click", () => sendBotMessage(btn.dataset.voiceSample));
  });

  document.querySelector("#bot-mic-btn")?.addEventListener("click", () => {
    startSpeechRecognition(
      transcript => {
        input.value = transcript;
        sendBotMessage(transcript);
      },
      msg => {
        if (voiceStatus) voiceStatus.textContent = msg;
      }
    );
  });

  document.querySelector("#bot-gps-btn")?.addEventListener("click", async () => {
    const applyCoords = async (lat, lon) => {
      const resp = await fetch(`/api/geocode?lat=${lat}&lon=${lon}`);
      if (!resp.ok) return;
      const loc = await resp.json();
      if (voiceStatus) {
        voiceStatus.textContent = `📍 GPS: ${loc.village_hi || loc.village} (${loc.block})`;
      }
      sendBotMessage(`${loc.block} गाँव ${loc.village}`);
    };
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        pos => applyCoords(pos.coords.latitude, pos.coords.longitude),
        () => applyCoords(29.8328, 77.8964),
        { timeout: 6000 }
      );
    } else {
      applyCoords(29.8328, 77.8964);
    }
  });
}

document.querySelector("[data-copy-link]")?.addEventListener("click", async () => {
  const status = document.querySelector("[data-copy-status]");
  try {
    await navigator.clipboard.writeText(location.href);
    status.textContent = text("Link copied.", "लिंक कॉपी हुआ।");
  } catch {
    status.textContent = text(
      "Copy failed. Copy the address from your browser.",
      "कॉपी विफल। ब्राउज़र से पता कॉपी करें।"
    );
  }
});

document.querySelectorAll("[data-gauge]").forEach(gauge => {
  const value = Math.max(0, Math.min(100, Number(gauge.dataset.gauge)));
  gauge.querySelector("span").style.left = `${value}%`;
});

document.querySelector("[data-print]")?.addEventListener("click", () => window.print());

const bighaPreset = document.querySelector("#bigha-preset");
const bighaInput = document.querySelector("#bigha-m2");
if (bighaPreset && bighaInput) {
  const match = [...bighaPreset.options].find(
    option => option.value && Number(option.value) === Number(bighaInput.value)
  );
  bighaPreset.value = match ? match.value : "";
  bighaPreset.addEventListener("change", () => {
    if (bighaPreset.value) bighaInput.value = bighaPreset.value;
    else bighaInput.focus();
  });
}

const standaloneUnit = document.querySelector("form[method=get] #area-unit");
if (standaloneUnit) {
  const field = document.querySelector("#bigha-field");
  const sync = () => {
    field.hidden = standaloneUnit.value !== "bigha";
  };
  standaloneUnit.addEventListener("change", sync);
  sync();
}

const cropSelect = document.querySelector("#crop");
const methodSelect = document.querySelector("#method");
if (cropSelect && methodSelect) {
  const filterMethods = () => {
    [...methodSelect.options].forEach(option => {
      if (!option.dataset.crops) return;
      const fits = option.dataset.crops.split(" ").includes(cropSelect.value);
      option.hidden = !fits;
      option.disabled = !fits;
      if (!fits && option.selected) methodSelect.value = "";
    });
  };
  cropSelect.addEventListener("change", filterMethods);
  filterMethods();
}

const drumToggle = document.querySelector("[data-drum-toggle]");
if (drumToggle) {
  const box = document.querySelector("[data-drum]");
  const litres = box.querySelector("[data-drum-litres]");
  const seconds = box.querySelector("[data-drum-seconds]");
  const result = box.querySelector("[data-drum-result]");
  drumToggle.addEventListener("click", () => {
    box.hidden = !box.hidden;
  });
  const compute = () => {
    const l = Number(litres.value);
    const s = Number(seconds.value);
    if (l > 0 && s > 0) {
      const flow = Math.round((l / s) * 100) / 100;
      document.querySelector("#flow-lps").value = flow;
      result.textContent = text(
        `≈ ${flow} L/s filled in above`,
        `≈ ${flow} लीटर/सेकंड ऊपर भर दिया`
      );
    }
  };
  litres.addEventListener("input", compute);
  seconds.addEventListener("input", compute);
}

document.querySelectorAll("[data-locate]").forEach(btn => {
  btn.addEventListener("click", () => {
    const status = document.querySelector("[data-locate-status]");
    const applyGps = async (lat, lon, fallbackNote = "") => {
      const latEl = document.querySelector("#lat");
      const lonEl = document.querySelector("#lon");
      if (latEl) latEl.value = lat.toFixed(4);
      if (lonEl) lonEl.value = lon.toFixed(4);
      try {
        const resp = await fetch(`/api/autofill?lat=${lat}&lon=${lon}`);
        if (resp.ok) {
          const data = await resp.json();
          const bSel = document.querySelector("#block-select");
          const vInp = document.querySelector("#village-input");
          if (bSel && data.location?.block) {
            bSel.value = data.location.block;
            bSel.dispatchEvent(new Event("change"));
          }
          if (vInp && data.location?.village) {
            vInp.value = data.location.village;
            vInp.dispatchEvent(new Event("change"));
          }
        }
      } catch {
        // Ignore network error
      }
      if (status) {
        status.textContent =
          fallbackNote ||
          text(
            `📍 GPS locked (${lat.toFixed(4)}, ${lon.toFixed(4)}) — village & soil auto-filled.`,
            `📍 GPS लोकेशन जुड़ गई (${lat.toFixed(4)}, ${lon.toFixed(4)}) — गाँव व मिट्टी स्वतः भर गए।`
          );
      }
    };
    if (!navigator.geolocation) {
      applyGps(
        29.8328,
        77.8964,
        text(
          "📍 Demo GPS locked to Dhandera, Roorkee (29.8328, 77.8964).",
          "📍 डेमो GPS: ढंडेरा, रुड़की (29.8328, 77.8964) स्वतः चुना गया।"
        )
      );
      return;
    }
    if (status) status.textContent = text("Finding location…", "लोकेशन खोज रहे हैं…");
    navigator.geolocation.getCurrentPosition(
      position => applyGps(position.coords.latitude, position.coords.longitude),
      () =>
        applyGps(
          29.8328,
          77.8964,
          text(
            "📍 Using Roorkee belt reference GPS (29.8328, 77.8964) — village & soil auto-filled.",
            "📍 रुड़की क्षेत्र संदर्भ GPS (29.8328, 77.8964) से गाँव व मिट्टी स्वतः भर गए।"
          )
        ),
      { timeout: 6000 }
    );
  });
});
