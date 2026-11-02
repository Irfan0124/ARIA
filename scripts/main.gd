extends Control

const BACKEND_URL := "http://127.0.0.1:8765"

@onready var status_label: Label = $Margin/Layout/Status
@onready var chat_log: RichTextLabel = $Margin/Layout/ChatLog
@onready var message_input: LineEdit = $Margin/Layout/InputRow/MessageInput
@onready var send_button: Button = $Margin/Layout/InputRow/SendButton
@onready var request: HTTPRequest = $BackendRequest

func _ready() -> void:
    send_button.pressed.connect(_send_message)
    message_input.text_submitted.connect(_on_text_submitted)
    request.request_completed.connect(_on_request_completed)
    _check_backend()

func _check_backend() -> void:
    var err := request.request(BACKEND_URL + "/health")
    if err != OK:
        status_label.text = "Backend belum tersedia. Jalankan Python backend."

func _on_text_submitted(_text: String) -> void:
    _send_message()

func _send_message() -> void:
    var message := message_input.text.strip_edges()
    if message.is_empty() or request.get_http_client_status() == HTTPClient.STATUS_REQUESTING:
        return

    chat_log.append_text("\n\n[b]Kamu:[/b] " + message.c_escape())
    message_input.clear()
    send_button.disabled = true
    status_label.text = "ARIA sedang berpikir..."

    var headers := PackedStringArray(["Content-Type: application/json"])
    var payload := JSON.stringify({"message": message})
    var err := request.request(BACKEND_URL + "/chat", headers, HTTPClient.METHOD_POST, payload)
    if err != OK:
        status_label.text = "Gagal menghubungi backend."
        send_button.disabled = false

func _on_request_completed(
    result: int,
    response_code: int,
    _headers: PackedStringArray,
    body: PackedByteArray
) -> void:
    send_button.disabled = false
    if result != HTTPRequest.RESULT_SUCCESS:
        status_label.text = "Koneksi backend gagal."
        return

    var parsed = JSON.parse_string(body.get_string_from_utf8())
    if response_code != 200:
        var detail := "Kesalahan backend."
        if parsed is Dictionary:
            detail = str(parsed.get("detail", detail))
        chat_log.append_text("\n[color=tomato]ARIA: " + detail.c_escape() + "[/color]")
        status_label.text = "Terjadi kesalahan."
        return

    if parsed is Dictionary:
        chat_log.append_text("\n[b]ARIA:[/b] " + str(parsed.get("reply", "")).c_escape())
        status_label.text = "ARIA siap."
    else:
        status_label.text = "Respons backend tidak valid."
