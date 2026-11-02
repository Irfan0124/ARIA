
extends Node2D

signal character_clicked
signal mood_changed(new_mood: String)

@onready var sprite: AnimatedSprite2D = $AnimatedSprite2D

var current_animation := ""

var is_dragging := false
var is_hovering := false

var drag_offset := Vector2.ZERO
var mouse_down_position := Vector2.ZERO
var drag_threshold := 8.0

# =========================
# AUTONOMOUS BEHAVIOR
# =========================

var idle_elapsed := 0.0
var next_idle_action := 12.0
var autonomous_remaining := 0.0
var is_autonomous := false

const SLEEP_AFTER := 60.0

# =========================
# PERSONALITY CORE
# =========================

var time_period := ""
var current_mood := "neutral"

var time_check_elapsed := 0.0
const TIME_CHECK_INTERVAL := 30.0

# =========================
# EMOTIONAL INTERACTION
# =========================

var mood_remaining := 0.0
var mood_is_temporary := false

const MOOD_DURATION := 90.0
const MOOD_RECOVERY_INTERVAL := 30.0


func _ready() -> void:
	randomize()
	update_time_period()
	idle()


func _process(delta: float) -> void:
	# Periksa waktu komputer
	time_check_elapsed += delta

	if time_check_elapsed >= TIME_CHECK_INTERVAL:
		time_check_elapsed = 0.0
		update_time_period()

	# Pemulihan mood sementara
	if mood_is_temporary:
		mood_remaining -= delta

		if mood_remaining <= 0.0:
			mood_is_temporary = false
			mood_remaining = 0.0
			update_mood()

	if is_dragging:
		return

	# Reaksi hover
	var mouse_inside := is_mouse_over_character()

	if mouse_inside and not is_hovering:
		is_hovering = true
		wake_up()

		if current_animation == "idle":
			play_autonomous("surprised", 2.0)

	elif not mouse_inside and is_hovering:
		is_hovering = false

		if is_autonomous:
			finish_autonomous()
		elif current_animation == "surprised":
			idle()

	# Timer animasi otomatis
	if is_autonomous:
		autonomous_remaining -= delta

		if autonomous_remaining <= 0.0:
			finish_autonomous()

		return

	# Jangan ganggu animasi dari main.gd
	if current_animation != "idle" and current_animation != "sleep":
		return

	idle_elapsed += delta

	# Tidur setelah tidak digunakan
	if idle_elapsed >= SLEEP_AFTER and current_animation != "sleep":
		play_autonomous("sleep", 999999.0)
		return

	# Aktivitas otomatis
	if idle_elapsed >= next_idle_action:
		perform_idle_action()


# =========================
# TIME AWARENESS
# =========================

func update_time_period() -> void:
	var system_time := Time.get_datetime_dict_from_system()
	var hour: int = system_time.hour

	var new_period := ""

	if hour >= 5 and hour < 11:
		new_period = "morning"
	elif hour >= 11 and hour < 17:
		new_period = "afternoon"
	elif hour >= 17 and hour < 19:
		new_period = "evening"
	else:
		new_period = "night"

	if time_period != new_period:
		time_period = new_period
		print("ARIA: Sekarang periode ", time_period)

		if not mood_is_temporary:
			update_mood()


func update_mood() -> void:
	var new_mood := "neutral"

	match time_period:
		"morning":
			new_mood = "happy"
		"afternoon":
			new_mood = "curious"
		"evening":
			new_mood = "relaxed"
		"night":
			new_mood = "sleepy"

	set_mood(new_mood)


func set_mood(new_mood: String) -> void:
	if current_mood == new_mood:
		return

	current_mood = new_mood

	print("ARIA Mood: ", current_mood)
	mood_changed.emit(current_mood)


# =========================
# EMOTIONAL INTERACTION
# =========================

func react_to_message(message: String) -> void:
	var text := message.to_lower()

	var new_mood := current_mood

	# Deteksi pujian dan sapaan ramah
	var happy_words: Array[String] = [
		"terima kasih", "makasih", "bagus", "hebat",
		"pintar", "keren", "cantik", "sayang",
		"aku suka", "halo", "hai"
	]

	# Deteksi rasa penasaran
	var curious_words: Array[String] = [
		"kenapa", "bagaimana", "mengapa", "apa itu",
		"jelaskan", "ceritakan", "menurutmu",
		"bagaimana jika", "bisakah"
	]

	# Deteksi percakapan santai
	var relaxed_words: Array[String] = [
		"santai", "istirahat", "ngobrol",
		"temani aku", "lagi apa", "apa kabar"
	]

	if contains_any(text, happy_words):
		new_mood = "happy"

	elif contains_any(text, curious_words):
		new_mood = "curious"

	elif contains_any(text, relaxed_words):
		new_mood = "relaxed"

	else:
		new_mood = "neutral"

	# Reset durasi mood sementara
	mood_is_temporary = true
	mood_remaining = MOOD_DURATION

	if new_mood == "neutral":
		# Percakapan biasa tidak memaksakan mood baru.
		mood_is_temporary = false
		mood_remaining = 0.0
		update_mood()
	else:
		set_mood(new_mood)

	# Interaksi membangunkan ARIA
	idle_elapsed = 0.0
	next_idle_action = randf_range(12.0, 22.0)

	if current_animation == "sleep":
		wake_up()

	print("ARIA bereaksi terhadap pesan: ", current_mood)


func contains_any(text: String, words: Array[String]) -> bool:
	for word in words:
		if text.contains(word):
			return true

	return false


# =========================
# AUTONOMOUS BEHAVIOR
# =========================

func perform_idle_action() -> void:
	var actions: Array[String] = []

	match current_mood:
		"happy":
			actions = ["wave", "surprised", "wave"]

		"curious":
			actions = ["surprised", "sit", "wave"]

		"relaxed":
			actions = ["sit", "idle", "wave"]

		"sleepy":
			actions = ["sleep", "sit", "sleep"]

		_:
			actions = ["wave", "sit", "surprised"]

	var selected_action: String = actions[
		randi_range(0, actions.size() - 1)
	]

	var duration := 3.0

	match selected_action:
		"wave":
			duration = 3.0
		"sit":
			duration = 5.0
		"surprised":
			duration = 2.0
		"sleep":
			duration = 8.0
		"idle":
			duration = 3.0

	play_autonomous(selected_action, duration)

	idle_elapsed = 0.0
	next_idle_action = randf_range(12.0, 22.0)


func play_autonomous(animation_name: String, duration: float) -> void:
	play_animation(animation_name)
	is_autonomous = true
	autonomous_remaining = duration


func finish_autonomous() -> void:
	is_autonomous = false
	autonomous_remaining = 0.0

	if not is_hovering:
		idle()


func wake_up() -> void:
	if current_animation == "sleep":
		idle_elapsed = 0.0
		next_idle_action = randf_range(12.0, 22.0)
		play_autonomous("surprised", 2.0)


# =========================
# MOUSE INTERACTION
# =========================

func _input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:

			if event.pressed:
				if is_mouse_over_character():
					wake_up()

					is_dragging = true
					mouse_down_position = get_global_mouse_position()
					drag_offset = global_position - mouse_down_position

					if is_autonomous:
						is_autonomous = false

					if current_animation == "surprised":
						idle()

					get_viewport().set_input_as_handled()

			else:
				if is_dragging:
					var moved_distance = mouse_down_position.distance_to(
						get_global_mouse_position()
					)

					is_dragging = false

					if moved_distance < drag_threshold:
						idle_elapsed = 0.0
						character_clicked.emit()

					get_viewport().set_input_as_handled()

	elif event is InputEventMouseMotion:
		if is_dragging:
			global_position = get_global_mouse_position() + drag_offset
			get_viewport().set_input_as_handled()


func is_mouse_over_character() -> bool:
	var mouse_position = sprite.to_local(
		sprite.get_global_mouse_position()
	)

	var frame_texture = sprite.sprite_frames.get_frame_texture(
		sprite.animation,
		sprite.frame
	)

	if frame_texture == null:
		return false

	var sprite_size = frame_texture.get_size()

	var click_rect = Rect2(
		-sprite_size / 2.0,
		sprite_size
	)

	return click_rect.has_point(mouse_position)


# =========================
# ANIMATION CONTROLLER
# =========================

func play_animation(animation_name: String) -> void:
	if not sprite.sprite_frames.has_animation(animation_name):
		push_warning("Animasi tidak ditemukan: " + animation_name)
		return

	if current_animation == animation_name and sprite.is_playing():
		return

	current_animation = animation_name
	sprite.play(animation_name)


func idle() -> void:
	is_autonomous = false
	play_animation("idle")


func thinking() -> void:
	is_autonomous = false
	play_animation("thinking")


func talking() -> void:
	is_autonomous = false
	play_animation("talk")


func waving() -> void:
	is_autonomous = false
	play_animation("wave")


func sleeping() -> void:
	is_autonomous = false
	play_animation("sleep")


func surprised() -> void:
	is_autonomous = false
	play_animation("surprised")


func walking() -> void:
	is_autonomous = false
	play_animation("walk")


func sitting() -> void:
	is_autonomous = false
	play_animation("sit")
