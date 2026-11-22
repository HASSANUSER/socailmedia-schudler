# Model and media notes

The proposed Arabic text and ASR model IDs are defaults, not guarantees of compatibility or quality on every machine. Validate each model on a short sample before batch processing.

This first version does not implement a vision-language model or OCR. It must not claim to have watched a video when it only has a title, description, or transcript. The UI includes a fallback transcript placeholder that instructs the generator not to invent content; users should reject such outputs or supply local media.

The 0.5B text model is intentionally small. Expect lower reasoning quality than larger models. For Islamic material, manually verify Qur'anic quotations, Hadith wording, attribution, authenticity grading, and religious rulings before publishing.
