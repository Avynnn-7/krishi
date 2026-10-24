import requests


class DeliveryError(RuntimeError):
    pass


def send_payload(config: dict, phone: str, content: dict) -> None:
    required = ("META_ACCESS_TOKEN", "META_PHONE_NUMBER_ID", "META_GRAPH_VERSION")
    if not all(config.get(key) for key in required):
        raise DeliveryError("Meta transport is not configured.")
    try:
        response = requests.post(
            f"https://graph.facebook.com/{config['META_GRAPH_VERSION']}/{config['META_PHONE_NUMBER_ID']}/messages",
            headers={"Authorization": f"Bearer {config['META_ACCESS_TOKEN']}"},
            json={"messaging_product": "whatsapp", "to": phone, **content},
            timeout=(3, 10),
        )
        response.raise_for_status()
        if not response.json().get("messages"):
            raise DeliveryError("Meta did not acknowledge the outgoing message.")
    except (requests.RequestException, ValueError) as exc:
        raise DeliveryError("WhatsApp delivery failed; retry is required.") from exc


def send_reply(config: dict, phone: str, reply: dict) -> None:
    if reply.get("document"):
        content = {
            "type": "document",
            "document": {
                "link": reply["document"],
                "caption": reply["text"],
                "filename": "jal-khadd.pdf",
            },
        }
    else:
        content = {"type": "text", "text": {"body": reply["text"]}}
    send_payload(config, phone, content)
