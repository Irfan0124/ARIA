
extends Control

const BACKEND_URL := "http://127.0.0.1:8765"
const TALK_DURATION := 2.0
const CONNECT_TIMEOUT := 10.0
@onready var mic_button: Button = $Margin/Layout/InputRow/MicButton
@onready var chat_log: RichTextLabel = $Margin/Layout/ChatLog
@onready var status_label: Label = $Margin/Layout/Status
@onready var message_input: LineEdit = $Margin/Layout/InputRow/MessageInput
@onready var send_button: Button = $Margin/Layout/InputRow/SendButton
@onready var request: HTTPRequest = $BackendRequest
@onready var aria_character = $AriaCharacter

var is_busy := false
var current_request := ""
var animation_session := 0
var chat_visible := false
var tray_request: HTTPRequest
var is_closing_to_tray := false
var stream_client: HTTPClient
var stream_buffer := ""
var stream_reply_started := false
var tray_tcp := StreamPeerTCP.new()
var tray_udp := PacketPeerUDP.new()
var tts_request: HTTPRequest
var audio_player: AudioStreamPlayer
var full_reply := ""
var tts_queue: Array[String] = []
var tts_sentence_buffer := ""
var tts_bracket_stack: Array[String] = []
var is_tts_request_active := false
var is_chat_stream_finished := false
var audio_queue: Array[AudioStreamWAV] = []
var mic_player: AudioStreamPlayer
var mic_capture: AudioEffectCapture
var is_stt_request_active := false
var is_recording := false
var recorded_audio := PackedVector2Array()
var stt_request: HTTPRequest
func _ready() -> void:
	send_button.pressed.connect(_send_message)
	mic_button.button_down.connect(_start_recording)
	mic_button.button_up.connect(_stop_recording)
	message_input.text_submitted.connect(_on_text_submitted)
	request.request_completed.connect(_on_request_completed)
	tts_request = HTTPRequest.new()
	tts_request.name = "TTSRequest"
	tts_request.timeout = 60.0
	add_child(tts_request)

	tts_request.request_completed.connect(_on_tts_completed)

	audio_player = AudioStreamPlayer.new()
	audio_player.name = "AriaAudioPlayer"
	add_child(audio_player)

	audio_player.finished.connect(_on_tts_finished)
	get_tree().set_auto_accept_quit(false)
	DisplayServer.window_set_title("ARIA")

	tray_request = HTTPRequest.new()
	tray_request.name = "Trayrequest"
	tray_request.timeout =2.0
	add_child(tray_request)


	if not aria_character.character_clicked.is_connected(_on_aria_character_clicked):
		aria_character.character_clicked.connect(_on_aria_character_clicked)

	$Margin.hide()
	_setup_microphone()
	_check_backend()
	_play_intro()

func _setup_microphone() -> void:
	var record_bus := AudioServer.get_bus_index("Record")

	if record_bus == -1:
		push_error("[ARIA STT] Audio Bus Record tidak ditemukan.")
		return

	mic_capture = AudioServer.get_bus_effect(
		record_bus,
		0
	) as AudioEffectCapture

	if mic_capture == null:
		push_error("[ARIA STT] AudioEffectCapture tidak ditemukan.")
		return

	mic_player = AudioStreamPlayer.new()
	mic_player.name = "MicrophonePlayer"
	mic_player.stream = AudioStreamMicrophone.new()
	mic_player.bus = "Record"
	add_child(mic_player)

	print("[ARIA STT] Mikrofon siap digunakan.")
func _process(_delta: float) -> void:
	if not is_recording or mic_capture == null:
		return

	var available := mic_capture.get_frames_available()

	if available > 0:
		var frames := mic_capture.get_buffer(available)
		recorded_audio.append_array(frames)

func _start_recording() -> void:
	if is_busy or mic_player == null or mic_capture == null:
		return

	recorded_audio.clear()
	mic_capture.clear_buffer()

	is_recording = true
	mic_player.play()

	mic_button.text = "🔴"
	status_label.text = "Mendengarkan..."

func _stop_recording() -> void:
	if not is_recording:
		return

	is_recording = false
	mic_player.stop()

	var available := mic_capture.get_frames_available()

	if available > 0:
		recorded_audio.append_array(
			mic_capture.get_buffer(available)
		)

	var peak := 0.0

	for sample in recorded_audio:
		peak = maxf(peak, absf(sample.x))
		peak = maxf(peak, absf(sample.y))

	print("[ARIA MIC] Jumlah sampel: ", recorded_audio.size())
	print("[ARIA MIC] Peak volume: ", peak)
	print("[ARIA MIC] Sample rate: ", AudioServer.get_mix_rate())

	mic_button.text = "🎙"
	mic_button.disabled = true

	if recorded_audio.size() < 1000:
		status_label.text = "Rekaman terlalu singkat."
		mic_button.disabled = false
		return

	status_label.text = "Memproses suara..."

	var wav_data := _create_wav(recorded_audio)

	_send_stt_audio(wav_data)

func _create_wav(samples: PackedVector2Array) -> PackedByteArray:
	var sample_rate := int(AudioServer.get_mix_rate())
	var channels := 2
	var bits_per_sample := 16
	var data_size := samples.size() * channels * 2

	var wav := StreamPeerBuffer.new()
	wav.big_endian = false

	wav.put_data("RIFF".to_utf8_buffer())
	wav.put_32(36 + data_size)
	wav.put_data("WAVE".to_utf8_buffer())

	wav.put_data("fmt ".to_utf8_buffer())
	wav.put_32(16)
	wav.put_16(1)
	wav.put_16(channels)
	wav.put_32(sample_rate)
	wav.put_32(sample_rate * channels * 2)
	wav.put_16(4)
	wav.put_16(bits_per_sample)

	wav.put_data("data".to_utf8_buffer())
	wav.put_32(data_size)

	for sample in samples:
		var left := clampf(sample.x, -1.0, 1.0)
		var right := clampf(sample.y, -1.0, 1.0)

		wav.put_16(roundi(left * 32767.0))
		wav.put_16(roundi(right * 32767.0))

	return wav.data_array

func _send_stt_audio(wav_data: PackedByteArray) -> void:
	if is_stt_request_active:
		return

	if stt_request == null:
		stt_request = HTTPRequest.new()
		stt_request.name = "STTRequest"
		stt_request.timeout = 120.0
		add_child(stt_request)
		stt_request.request_completed.connect(_on_stt_completed)

	var boundary := "----ARIASTTBoundary123456"

	var body := PackedByteArray()

	body.append_array(
		("--" + boundary + "\r\n").to_utf8_buffer()
	)
	body.append_array(
		("Content-Disposition: form-data; name=\"audio\"; filename=\"recording.wav\"\r\n").to_utf8_buffer()
	)
	body.append_array(
		"Content-Type: audio/wav\r\n\r\n".to_utf8_buffer()
	)
	body.append_array(wav_data)
	body.append_array(
		("\r\n--" + boundary + "--\r\n").to_utf8_buffer()
	)

	var headers := PackedStringArray([
		"Content-Type: multipart/form-data; boundary=" + boundary
	])

	is_stt_request_active = true

	var err := stt_request.request_raw(
		BACKEND_URL + "/stt",
		headers,
		HTTPClient.METHOD_POST,
		body
	)

	if err != OK:
		is_stt_request_active = false
		mic_button.disabled = false
		status_label.text = "Gagal mengirim audio."
		push_error("[ARIA STT] Request gagal: " + str(err))

func _on_stt_completed(
	result: int,
	response_code: int,
	_headers: PackedStringArray,
	body: PackedByteArray
) -> void:
	is_stt_request_active = false

	if result != HTTPRequest.RESULT_SUCCESS or response_code != 200:
		status_label.text = "Transkripsi gagal."
		push_error("[ARIA STT] HTTP: " + str(response_code))
		push_error(body.get_string_from_utf8())
		mic_button.disabled = false
		return

	var response: Variant = JSON.parse_string(
		body.get_string_from_utf8()
	)

	if not response is Dictionary:
		status_label.text = "Respons STT tidak valid."
		mic_button.disabled = false
		return

	var transcribed_text := str(response.get("text", "")).strip_edges()

	if transcribed_text.is_empty():
		status_label.text = "Suara tidak terdeteksi."
		mic_button.disabled = false
		return

	message_input.text = transcribed_text
	status_label.text = "Suara berhasil dikenali."

	_send_message()

func _maybe_finish_tts_stream() -> void:
	if not is_chat_stream_finished:
		return

	if is_tts_request_active:
		return

	if not tts_queue.is_empty():
		return

	if not audio_queue.is_empty():
		return

	if audio_player.playing:
		return

	_finish_request()
	status_label.text = "ARIA siap."
	set_aria_animation("idle")

func _play_next_audio() -> void:
	if audio_player.playing:
		return

	if audio_queue.is_empty():
		_maybe_finish_tts_stream()
		return

	var next_audio: AudioStreamWAV = audio_queue.pop_front()

	audio_player.stream = next_audio
	audio_player.play()

	status_label.text = "ARIA sedang berbicara..."
	set_aria_animation("talk")

func _start_next_tts_request() -> void:
	if is_tts_request_active or tts_queue.is_empty():
		return

	var sentence: String = tts_queue.pop_front()
	var payload := JSON.stringify({"text": sentence})
	var headers := PackedStringArray(["Content-Type: application/json"])

	is_tts_request_active = true

	var err := tts_request.request(
		BACKEND_URL + "/tts",
		headers,
		HTTPClient.METHOD_POST,
		payload
	)

	if err != OK:
		is_tts_request_active = false
		push_error("Gagal mengirim permintaan TTS.")
		_start_next_tts_request()

func _append_tts_text(token: String) -> void:
	for i in range(token.length()):
		var character := token.substr(i, 1)

		# Deteksi tanda kurung pembuka
		if character == "(":
				tts_bracket_stack.append(")")
				continue
		elif character == "[":
				tts_bracket_stack.append("]")
				continue
		elif character == "{":
				tts_bracket_stack.append("}")
				continue

		# Jika sedang berada di dalam tanda kurung,
		# abaikan semua karakter sampai penutup ditemukan.
		if not tts_bracket_stack.is_empty():
			if character == tts_bracket_stack.back():
				tts_bracket_stack.pop_back()
			continue

		tts_sentence_buffer += character

func _queue_completed_sentences() -> void:
	while true:
		var boundary := -1

		for i in range(tts_sentence_buffer.length() - 1):
			var character := tts_sentence_buffer.substr(i, 1)
			var next_character := tts_sentence_buffer.substr(i + 1, 1)

			if character in [".", "!", "?", ",", "。", "！", "？", "，"] \
			and next_character in [" ", "\n", "\t"]:
				boundary = i + 1
				break

		if boundary == -1:
			break

		var sentence := tts_sentence_buffer.substr(0, boundary).strip_edges()

		if has_speakable_text(sentence):
			tts_queue.append(sentence)

		tts_sentence_buffer = tts_sentence_buffer.substr(boundary).strip_edges()

	_start_next_tts_request()
# =========================
# INTERAKSI KARAKTER
# =========================

func _on_aria_character_clicked() -> void:
	if chat_visible:
		$Margin.hide()
		chat_visible = false

		if not is_busy:
			set_aria_animation("idle")
	else:
		$Margin.show()
		chat_visible = true

		if not is_busy:
			set_aria_animation("wave")


func _play_intro() -> void:
	set_aria_animation("wave")

	var intro_session := animation_session

	await get_tree().create_timer(2.0).timeout

	if intro_session == animation_session and not is_busy:
		set_aria_animation("idle")


# =========================
# BACKEND
# =========================

func _check_backend() -> void:
	current_request = "health"
	status_label.text = "Memeriksa backend..."

	var err := request.request(BACKEND_URL + "/health")

	if err != OK:
		current_request = ""
		status_label.text = "Backend belum tersedia."


func _on_request_completed(
	result: int,
	response_code: int,
	_headers: PackedStringArray,
	_body: PackedByteArray
) -> void:

	if current_request != "health":
		return

	current_request = ""

	if result == HTTPRequest.RESULT_SUCCESS and response_code == 200:
		status_label.text = "ARIA siap."
	else:
		status_label.text = "Backend tidak merespons."


func _on_text_submitted(_text: String) -> void:
	_send_message()


# =========================
# CHAT
# =========================

func _send_message() -> void:
	var message := message_input.text.strip_edges()

	if message.is_empty() or is_busy:
		return

	audio_player.stop()

	tts_queue.clear()
	audio_queue.clear()
	tts_sentence_buffer = ""
	tts_bracket_stack.clear()
	is_tts_request_active = false
	is_chat_stream_finished = false

	full_reply = ""

	is_busy = true
	current_request = "chat"

	aria_character.react_to_message(message)

	chat_log.append_text(
		"\n\n[b]Kamu:[/b] " + message.c_escape()
	)

	chat_log.append_text("\n[b]ARIA:[/b] ")

	message_input.clear()
	send_button.disabled = true
	mic_button.disabled = true
	status_label.text = "ARIA sedang berpikir..."

	set_aria_animation("thinking")

	var payload := JSON.stringify({
		"message": message,
		"mood": aria_character.current_mood,
		"time_period": aria_character.time_period
	})

	_stream_chat(payload)

# =========================
# STREAMING
# =========================

func _stream_chat(payload: String) -> void:
	stream_client = HTTPClient.new()
	stream_buffer = ""
	stream_reply_started = false

	var err := stream_client.connect_to_host("127.0.0.1", 8765)

	if err != OK:
		_stream_failed("Tidak dapat menghubungi backend.")
		return

	var start_time := Time.get_ticks_msec()

	while stream_client.get_status() != HTTPClient.STATUS_CONNECTED:
		stream_client.poll()

		var connection_status := stream_client.get_status()

		if connection_status == HTTPClient.STATUS_CANT_CONNECT \
		or connection_status == HTTPClient.STATUS_CANT_RESOLVE \
		or connection_status == HTTPClient.STATUS_CONNECTION_ERROR:
			_stream_failed("Gagal terhubung ke backend.")
			return

		if Time.get_ticks_msec() - start_time > int(CONNECT_TIMEOUT * 1000):
			_stream_failed("Waktu koneksi backend habis.")
			return

		await get_tree().process_frame

	var headers := PackedStringArray([
		"Content-Type: application/json",
        "Accept: application/x-ndjson"
	])

	err = stream_client.request(
		HTTPClient.METHOD_POST,
		"/chat/stream",
		headers,
		payload
	)

	if err != OK:
		_stream_failed("Gagal mengirim pesan.")
		return

	var response_started := false

	while true:
		stream_client.poll()

		var connection_status := stream_client.get_status()

		if connection_status == HTTPClient.STATUS_BODY:
			if not response_started:
				response_started = true

				var response_code := stream_client.get_response_code()

				if response_code != 200:
					_stream_failed(
						"Backend mengembalikan HTTP " + str(response_code)
					)
					return

	

			var chunk := stream_client.read_response_body_chunk()

			if not chunk.is_empty():
				stream_buffer += chunk.get_string_from_utf8()
				_process_stream_lines()

		elif connection_status == HTTPClient.STATUS_CONNECTED:
			if response_started:
				break

		elif connection_status == HTTPClient.STATUS_CONNECTION_ERROR \
		or connection_status == HTTPClient.STATUS_CANT_CONNECT \
		or connection_status == HTTPClient.STATUS_DISCONNECTED:
			_stream_failed("Koneksi streaming terputus.")
			return

		await get_tree().process_frame

	if not stream_buffer.is_empty():
		_process_stream_line(stream_buffer.strip_edges())
		stream_buffer = ""

	_finish_stream()


func _process_stream_lines() -> void:
	while stream_buffer.contains("\n"):
		var newline_index := stream_buffer.find("\n")

		var line := stream_buffer.substr(0, newline_index).strip_edges()

		stream_buffer = stream_buffer.substr(newline_index + 1)

		if not line.is_empty():
			_process_stream_line(line)


func _process_stream_line(line: String) -> void:
	var parsed: Variant = JSON.parse_string(line)

	if not parsed is Dictionary:
		return

	if parsed.has("error"):
		push_warning("Streaming error: " + str(parsed["error"]))
		return

	var message_data: Variant = parsed.get("message", {})

	if message_data is Dictionary:
		var token := str(message_data.get("content", ""))

		if not token.is_empty():
			if not stream_reply_started:
				stream_reply_started = true
				status_label.text = "ARIA sedang berbicara..."
				set_aria_animation("talk")

			full_reply += token
			_append_tts_text(token)
			_queue_completed_sentences()

			chat_log.append_text(token.c_escape())
			chat_log.scroll_to_line(chat_log.get_line_count())

func _finish_stream() -> void:
	var remaining_sentence := tts_sentence_buffer.strip_edges()

	if has_speakable_text(remaining_sentence):
		tts_queue.append(remaining_sentence)

	tts_sentence_buffer = ""
	tts_bracket_stack.clear()
	is_chat_stream_finished = true

	_start_next_tts_request()
	_maybe_finish_tts_stream()






func _on_tts_completed(
	result: int,
	response_code: int,
	_headers: PackedStringArray,
	body: PackedByteArray
) -> void:
	is_tts_request_active = false

	if result != HTTPRequest.RESULT_SUCCESS:
		push_error("Permintaan Supertonic gagal.")
		push_error("Hasil request: " + str(result))

	elif response_code == 204:
		print("[ARIA TTS] Teks kosong dilewati.")

	elif response_code != 200:
		push_error("Supertonic HTTP: " + str(response_code))
		push_error(body.get_string_from_utf8())

	else:
		var wav := AudioStreamWAV.load_from_buffer(body)

		if wav != null:
			audio_queue.append(wav)
		else:
			push_error("Gagal membaca audio WAV.")

	_start_next_tts_request()
	_play_next_audio()
	_maybe_finish_tts_stream()


func _on_tts_finished() -> void:
	_play_next_audio()
	_maybe_finish_tts_stream()
	

func has_speakable_text(text: String) -> bool:
	var regex := RegEx.new()
	regex.compile("[\\p{L}\\p{N}]")
	return regex.search(text) != null

func _stream_failed(error_message: String) -> void:
	tts_queue.clear()
	audio_queue.clear()
	tts_sentence_buffer = ""

	is_chat_stream_finished = false

	audio_player.stop()
	if tts_request.get_http_client_status() != HTTPClient.STATUS_DISCONNECTED:
		tts_request.cancel_request()
	
		is_tts_request_active = false

	chat_log.append_text(
		"\n[color=tomato]" + error_message.c_escape() + "[/color]"
	)

	status_label.text = "Streaming gagal."

	_finish_request()
	set_aria_animation("idle")


# =========================
# SISTEM ANIMASI
# =========================

func set_aria_animation(animation_name: String) -> void:
	animation_session += 1

	match animation_name:
		"idle":
			aria_character.idle()
		"thinking":
			aria_character.thinking()
		"talk":
			aria_character.talking()
		"wave":
			aria_character.waving()
		"sleep":
			aria_character.sleeping()
		"surprised":
			aria_character.surprised()
		"walk":
			aria_character.walking()
		"sit":
			aria_character.sitting()
		_:
			push_warning("Status animasi tidak dikenal: " + animation_name)


func _finish_request() -> void:
	is_busy = false
	current_request = ""

	send_button.disabled = false
	mic_button.disabled = false
	mic_button.text = "🎙"
func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST:
		if is_closing_to_tray:
			return

		is_closing_to_tray = true

		tray_udp.set_dest_address("127.0.0.1", 8767)

		var message := "hide:" + str(OS.get_process_id())
		var err := tray_udp.put_packet(message.to_utf8_buffer())

		if err != OK:
			push_error("Gagal mengirim perintah ke System Tray.")
			DisplayServer.window_set_mode(
				DisplayServer.WINDOW_MODE_MINIMIZED
			)

		is_closing_to_tray = false
