export const BODHAN_VOICES = [
  { name: "Prastuti", lang: "as", mf: "female" }, { name: "Ankur", lang: "as", mf: "male" },
  { name: "Ishita", lang: "bn", mf: "female" }, { name: "Sourav", lang: "bn", mf: "male" },
  { name: "Gwrbw", lang: "brx", mf: "female" }, { name: "Sansuma", lang: "brx", mf: "male" },
  { name: "Preeti", lang: "doi", mf: "female" }, { name: "Sham", lang: "doi", mf: "male" },
  { name: "Dhara", lang: "gu", mf: "female" }, { name: "Parth", lang: "gu", mf: "male" },
  { name: "Kavya", lang: "hi", mf: "female" }, { name: "Suhani", lang: "hi", mf: "female" }, { name: "Amit", lang: "hi", mf: "male" },
  { name: "Deepika", lang: "kn", mf: "female" }, { name: "Adarsh", lang: "kn", mf: "male" },
  { name: "Anjali", lang: "kok", mf: "female" }, { name: "Sandeep", lang: "kok", mf: "male" },
  { name: "Zoon", lang: "ks", mf: "female" }, { name: "Ishfaq", lang: "ks", mf: "male" },
  { name: "Vaidehi", lang: "mai", mf: "female" }, { name: "Madhukar", lang: "mai", mf: "male" },
  { name: "Lakshmi", lang: "ml", mf: "female" }, { name: "Kiran", lang: "ml", mf: "male" },
  { name: "Thoibi", lang: "mni", mf: "female" }, { name: "Chaoba", lang: "mni", mf: "male" },
  { name: "Anagha", lang: "mr", mf: "female" }, { name: "Chinmay", lang: "mr", mf: "male" },
  { name: "Srijana", lang: "ne", mf: "female" }, { name: "Sagar", lang: "ne", mf: "male" },
  { name: "Itishree", lang: "or", mf: "female" }, { name: "Akash", lang: "or", mf: "male" },
  { name: "Kaur", lang: "pa", mf: "female" }, { name: "Manpreet", lang: "pa", mf: "male" },
  { name: "Bharati", lang: "sa", mf: "female" }, { name: "Aryaman", lang: "sa", mf: "male" },
  { name: "Phulmani", lang: "sat", mf: "female" }, { name: "Sibu", lang: "sat", mf: "male" },
  { name: "Moomal", lang: "sd", mf: "female" }, { name: "Rano", lang: "sd", mf: "male" },
  { name: "Anitha", lang: "ta", mf: "female" }, { name: "Arun", lang: "ta", mf: "male" },
  { name: "Sravani", lang: "te", mf: "female" }, { name: "Vamsi", lang: "te", mf: "male" },
  { name: "Saba", lang: "ur", mf: "female" }, { name: "Zaid", lang: "ur", mf: "male" },
];

export const BODHAN_LANGS = [
  ["as", "Assamese"], ["bn", "Bengali"], ["brx", "Bodo"], ["doi", "Dogri"], ["en", "English"],
  ["gu", "Gujarati"], ["hi", "Hindi"], ["kn", "Kannada"], ["kok", "Konkani"], ["ks", "Kashmiri"],
  ["mai", "Maithili"], ["ml", "Malayalam"], ["mni", "Manipuri"], ["mr", "Marathi"], ["ne", "Nepali"],
  ["or", "Odia"], ["pa", "Punjabi"], ["sa", "Sanskrit"], ["sat", "Santali"], ["sd", "Sindhi"],
  ["ta", "Tamil"], ["te", "Telugu"], ["ur", "Urdu"],
];

export const BODHAN_STYLES = [
  "news", "TV style news", "AIR style news", "advertisements", "anger", "children's stories",
  "Customer Care", "disgust", "educational lecture", "fear", "happy", "sad",
  "single person narration audiobook", "surprise",
];

export const QWEN_SPEAKERS = [
  { name: "Ryan", desc: "Dynamic male voice with strong rhythmic drive (English)" },
  { name: "Aiden", desc: "Sunny American male voice with a clear midrange (English)" },
  { name: "Vivian", desc: "Bright, slightly edgy young female voice (Chinese)" },
  { name: "Serena", desc: "Warm, gentle young female voice (Chinese)" },
  { name: "Uncle_Fu", desc: "Seasoned male voice with a low, mellow timbre (Chinese)" },
  { name: "Dylan", desc: "Youthful Beijing male voice, clear natural timbre (Chinese)" },
  { name: "Eric", desc: "Lively Chengdu male voice, slightly husky brightness (Chinese)" },
  { name: "Ono_Anna", desc: "Playful Japanese female voice, light and nimble (Japanese)" },
  { name: "Sohee", desc: "Warm Korean female voice with rich emotion (Korean)" },
];

export const VOICE_DESIGN_DIMS = [
  ["Gender", "male / female / neutral"],
  ["Age", 'specific ages ("8 years old") or ranges (child 5-12, teenager, young adult 19-35, middle-aged 36-55, elderly 55+)'],
  ["Pitch", "high / medium / low"],
  ["Pace", "fast / medium / slow"],
  ["Emotion", "cheerful, calm, gentle, serious, lively, composed, soothing"],
  ["Characteristics", "magnetic, crisp, hoarse, mellow, sweet, rich, powerful"],
  ["Use case", "news broadcast, audiobook, animation, documentary narration"],
];

export const VOICE_DESIGN_NOTE = [
  "Be specific (use \u201cdeep\u201d, \u201ccrisp\u201d, \u201cfast-paced\u201d \u2014 not \u201cnice\u201d).",
  "Use multiple dimensions at once.",
  "Describe physical voice qualities, not feelings.",
  "No celebrity imitation (explicitly blocked).",
  "Concise \u2014 every word should serve a purpose.",
].join(" ");

export const BODHAN_REF_URL = "https://console.bodhan.ai/api-docs/#text-to-speech-api";