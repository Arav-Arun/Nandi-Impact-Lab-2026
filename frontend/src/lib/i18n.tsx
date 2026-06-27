/** Lightweight i18n. English is the primary language; the header language
 *  switcher swaps the UI to Marathi or Hindi. tr(key) falls back to English
 *  when a translation is missing, so the site is always coherent English by
 *  default and the toggle translates the covered strings. */
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export const INTAKE_LANGUAGES = [
  { code: "mr-IN", label: "Marathi" },
  { code: "hi-IN", label: "Hindi" },
  { code: "bn-IN", label: "Bengali" },
  { code: "te-IN", label: "Telugu" },
  { code: "ta-IN", label: "Tamil" },
  { code: "kn-IN", label: "Kannada" },
  { code: "gu-IN", label: "Gujarati" },
  { code: "en-IN", label: "English" },
] as const;

export type Lang = "en" | "mr" | "hi";
export const LANGS: { code: Lang; label: string }[] = [
  { code: "en", label: "English" },
  { code: "mr", label: "मराठी" },
  { code: "hi", label: "हिंदी" },
];

type Tri = { en: string; mr?: string; hi?: string };

const D: Record<string, Tri> = {
  // ── chrome ──
  "app.tagline": { en: "Bringing the lost back home", mr: "हरवलेल्यांना घरी आणत आहोत", hi: "खोए हुओं को घर ला रहे हैं" },
  "app.place": { en: "Simhastha Kumbh Mela 2027 · Nashik, Trimbakeshwar" },
  "nav.overview": { en: "Overview", mr: "आढावा", hi: "अवलोकन" },
  "nav.report": { en: "Report", mr: "तक्रार", hi: "रिपोर्ट" },
  "nav.operator": { en: "Operator", mr: "कक्ष", hi: "कक्ष" },
  "nav.blast": { en: "Blast", mr: "सूचना", hi: "सूचना" },
  "lang.label": { en: "Language", mr: "भाषा", hi: "भाषा" },

  // ── shared ──
  "s.live": { en: "Live", mr: "थेट", hi: "लाइव" },
  "s.reconnecting": { en: "Reconnecting", mr: "पुन्हा जोडत आहे", hi: "पुनः जुड़ रहा है" },
  "s.captured": { en: "captured", mr: "नोंदवले", hi: "दर्ज" },
  "s.nameUnknown": { en: "Name unknown", mr: "नाव अज्ञात", hi: "नाम अज्ञात" },
  "s.loading": { en: "Loading", mr: "लोड होत आहे", hi: "लोड हो रहा है" },
  "s.close": { en: "close", mr: "बंद करा", hi: "बंद करें" },
  "s.missing": { en: "Missing", mr: "हरवलेली", hi: "लापता" },
  "s.found": { en: "Found", mr: "सापडलेली", hi: "मिली" },
  "s.foundPerson": { en: "found person", mr: "सापडलेली व्यक्ती", hi: "मिला व्यक्ति" },

  // ── overview ──
  "ov.title": { en: "Bring the lost back home", mr: "हरवलेल्यांना पुन्हा घरी आणूया", hi: "खोए हुओं को घर वापस लाएँ" },
  "ov.sub": {
    en: "Families report a missing person in any language, by voice, WhatsApp, Telegram or a booth. NANDI turns it into a searchable case in seconds.",
    mr: "कुटुंबे कोणत्याही भाषेत आवाज, व्हॉट्सअ‍ॅप, टेलिग्राम किंवा बूथवरून तक्रार नोंदवतात. नंदी ती काही सेकंदात शोधण्यायोग्य केसमध्ये रूपांतरित करते.",
    hi: "परिवार किसी भी भाषा में आवाज़, व्हाट्सएप, टेलीग्राम या बूथ से रिपोर्ट करते हैं. नंदी उसे कुछ सेकंड में खोजने-योग्य केस बना देती है.",
  },
  "ov.total": { en: "Total reports", mr: "एकूण नोंदी", hi: "कुल रिपोर्ट" },
  "ov.live": { en: "captured live", mr: "थेट नोंदवले", hi: "लाइव दर्ज" },
  "ov.reunited": { en: "Reunited", mr: "पुन्हा भेट", hi: "पुनर्मिलन" },
  "ov.families": { en: "families", mr: "कुटुंबे", hi: "परिवार" },
  "ov.avg": { en: "Avg. reunion", mr: "सरासरी वेळ", hi: "औसत समय" },
  "ov.avgSub": { en: "report to handoff", mr: "नोंद ते सुपूर्द", hi: "रिपोर्ट से सौंपने तक" },
  "ov.dupes": { en: "Duplicates caught", mr: "दुहेरी नोंदी", hi: "डुप्लिकेट पकड़े" },
  "ov.dupesSub": { en: "same person, many centers", mr: "एकच व्यक्ती, अनेक केंद्रे", hi: "एक ही व्यक्ति, कई केंद्र" },

  "ov.metrics": { en: "Operational metrics", mr: "कार्यात्मक मेट्रिक्स", hi: "परिचालन मेट्रिक्स" },
  "ov.metricsHint": { en: "the real failures this system fixes", mr: "ही प्रणाली सोडवत असलेल्या खऱ्या त्रुटी", hi: "यह प्रणाली जो वास्तविक समस्याएँ हल करती है" },
  "m.cross": { en: "Cross-center matches", mr: "केंद्रांदरम्यान जुळण्या", hi: "केंद्रों के बीच मिलान" },
  "m.crossD": { en: "matched across different reporting centers", mr: "वेगवेगळ्या केंद्रांमध्ये जुळवले", hi: "अलग-अलग केंद्रों के बीच मिलान" },
  "m.dupe": { en: "Duplicate reports detected", mr: "दुहेरी नोंदी आढळल्या", hi: "डुप्लिकेट रिपोर्ट मिलीं" },
  "m.dupeD": { en: "likely the same person, filed twice", mr: "बहुधा एकच व्यक्ती, दोनदा नोंद", hi: "संभवतः एक ही व्यक्ति, दो बार दर्ज" },
  "m.noName": { en: "Cases without a name", mr: "नावाशिवाय नोंदी", hi: "बिना नाम केस" },
  "m.noNameD": { en: "still fully searchable", mr: "तरीही पूर्ण शोधण्यायोग्य", hi: "फिर भी पूरी तरह खोजने-योग्य" },
  "m.noPhone": { en: "Cases without a phone", mr: "फोनशिवाय नोंदी", hi: "बिना फोन केस" },
  "m.noPhoneD": { en: "no reliable contact assumed", mr: "विश्वसनीय संपर्क गृहीत नाही", hi: "विश्वसनीय संपर्क नहीं माना" },
  "m.escal": { en: "Needs escalation", mr: "तातडीची गरज", hi: "एस्केलेशन आवश्यक" },
  "m.escalD": { en: "open past the response window", mr: "प्रतिसाद वेळेनंतरही उघडे", hi: "प्रतिक्रिया समय के बाद भी खुले" },
  "m.risk": { en: "High-risk, unresolved", mr: "उच्च-धोका, अनिर्णीत", hi: "उच्च-जोखिम, अनसुलझे" },
  "m.riskD": { en: "children and elders still open", mr: "लहान मुले व वृद्ध अजून उघडे", hi: "बच्चे और बुज़ुर्ग अब भी खुले" },

  "ov.perDay": { en: "Reports per day", mr: "दररोज नोंदी", hi: "प्रतिदिन रिपोर्ट" },
  "ov.perDayHint": { en: "filed, by date", mr: "तारखेनुसार नोंदवले", hi: "तिथि अनुसार दर्ज" },
  "ov.byAge": { en: "Who goes missing, by age", mr: "वयानुसार कोण हरवते", hi: "उम्र अनुसार कौन खोता है" },
  "ov.byAgeHint": { en: "elders at highest risk", mr: "वृद्ध सर्वाधिक धोक्यात", hi: "बुज़ुर्ग सर्वाधिक जोखिम में" },
  "ov.outcomes": { en: "Case outcomes", mr: "केसचे निकाल", hi: "केस परिणाम" },
  "ov.languages": { en: "Languages spoken", mr: "बोलल्या जाणाऱ्या भाषा", hi: "बोली जाने वाली भाषाएँ" },
  "ov.languagesHint": { en: "why native-language intake matters", mr: "मातृभाषेतील नोंद का महत्त्वाची", hi: "मातृभाषा में दर्ज क्यों ज़रूरी" },
  "ov.channels": { en: "Where reports arrive", mr: "नोंदी कुठून येतात", hi: "रिपोर्ट कहाँ से आती हैं" },
  "ov.hotspots": { en: "Hotspots, last seen", mr: "हॉटस्पॉट, शेवटचे ठिकाण", hi: "हॉटस्पॉट, अंतिम स्थान" },
  "ov.hotspotsHint": { en: "where separations cluster", mr: "विभक्त होण्याची ठिकाणे", hi: "जहाँ बिछड़ना केंद्रित" },

  // ── report / intake ──
  "in.title": { en: "Report a missing person", mr: "हरवलेल्या व्यक्तीची तक्रार", hi: "लापता व्यक्ति की रिपोर्ट" },
  "in.sub": { en: "No field is required. Just tell us what you remember.", mr: "कोणतेही क्षेत्र आवश्यक नाही. फक्त आठवते ते सांगा.", hi: "कोई फ़ील्ड ज़रूरी नहीं. बस जो याद है बताएँ." },
  "in.speak": { en: "Speak in your language", mr: "तुमच्या भाषेत बोला", hi: "अपनी भाषा में बोलें" },
  "in.stopSpeaking": { en: "Stop recording", mr: "रेकॉर्डिंग थांबवा", hi: "रिकॉर्डिंग रोकें" },
  "in.speakHint": { en: "Speak in any language. We fill the form for you.", mr: "कोणत्याही भाषेत बोला. आम्ही फॉर्म भरतो.", hi: "किसी भी भाषा में बोलें. हम फॉर्म भर देंगे." },
  "in.recording": { en: "Recording. Tap to stop.", mr: "रेकॉर्ड होत आहे. थांबवण्यासाठी टॅप करा.", hi: "रिकॉर्ड हो रहा है. रोकने के लिए टैप करें." },
  "in.transcribing": { en: "Transcribing", mr: "लिप्यंतर करत आहे", hi: "लिप्यंतरण हो रहा है" },
  "in.understanding": { en: "Understanding", mr: "समजून घेत आहे", hi: "समझ रहे हैं" },
  "in.orType": { en: "Or type freely in any language", mr: "किंवा कोणत्याही भाषेत मोकळेपणाने लिहा", hi: "या किसी भी भाषा में लिखें" },
  "in.typePlaceholder": { en: "e.g. my father is missing, 72 years, saffron kurta, near Ramkund", mr: "उदा. माझे वडील हरवले, ७२ वर्षे, भगवा कुर्ता, रामकुंडजवळ", hi: "उदा. मेरे पिता लापता हैं, 72 वर्ष, भगवा कुर्ता, रामकुंड के पास" },
  "in.autofill": { en: "Autofill", mr: "भरून घ्या", hi: "स्वतः भरें" },
  "in.heard": { en: "heard", mr: "ऐकले", hi: "सुना" },
  "in.confidence": { en: "confidence", mr: "विश्वास", hi: "विश्वास" },
  "in.autofilled": { en: "Fields below were filled automatically. Please check and correct.", mr: "खालील क्षेत्रे आपोआप भरली. कृपया तपासा व दुरुस्त करा.", hi: "नीचे के फ़ील्ड अपने-आप भरे गए. कृपया जाँचें व सुधारें." },
  "in.name": { en: "Name (if known)", mr: "नाव (माहित असल्यास)", hi: "नाम (यदि ज्ञात हो)" },
  "in.namePlaceholder": { en: "e.g. Ramesh Patil", mr: "उदा. रमेश पाटील", hi: "उदा. रमेश पाटील" },
  "in.gender": { en: "Gender", mr: "लिंग", hi: "लिंग" },
  "in.male": { en: "Male", mr: "पुरुष", hi: "पुरुष" },
  "in.female": { en: "Female", mr: "स्त्री", hi: "महिला" },
  "in.unknown": { en: "Unknown", mr: "माहीत नाही", hi: "अज्ञात" },
  "in.ageGroup": { en: "Age group", mr: "वयोगट", hi: "आयु वर्ग" },
  "in.lastSeen": { en: "Last seen where?", mr: "शेवटी कुठे दिसले?", hi: "अंतिम बार कहाँ देखा?" },
  "in.lastSeenPlaceholder": { en: "e.g. Ramkund ghat", mr: "उदा. रामकुंड घाट", hi: "उदा. रामकुंड घाट" },
  "in.desc": { en: "What were they wearing / what do they look like?", mr: "ते काय परिधान केले होते / कसे दिसतात?", hi: "उन्होंने क्या पहना था / कैसे दिखते हैं?" },
  "in.descPlaceholder": { en: "e.g. saffron kurta, white dhoti, rudraksha mala", mr: "उदा. भगवा कुर्ता, पांढरे धोतर, रुद्राक्ष माळ", hi: "उदा. भगवा कुर्ता, सफेद धोती, रुद्राक्ष माला" },
  "in.state": { en: "State", mr: "राज्य", hi: "राज्य" },
  "in.mobile": { en: "Your mobile", mr: "तुमचा मोबाईल", hi: "आपका मोबाइल" },
  "in.submit": { en: "File report", mr: "तक्रार नोंदवा", hi: "रिपोर्ट दर्ज करें" },
  "in.filing": { en: "Filing", mr: "नोंद होत आहे", hi: "दर्ज हो रहा है" },
  "in.privacy": { en: "Your number is stored masked.", mr: "तुमचा नंबर मास्क करून ठेवला जातो.", hi: "आपका नंबर मास्क करके रखा जाता है." },
  "in.filed": { en: "Report filed", mr: "नोंद झाली", hi: "रिपोर्ट दर्ज" },
  "in.filedSub": { en: "Your report is filed and searchable across all centers.", mr: "तुमची नोंद झाली असून सर्व केंद्रांवर शोधण्यायोग्य आहे.", hi: "आपकी रिपोर्ट दर्ज है और सभी केंद्रों पर खोजने-योग्य है." },
  "in.fileAnother": { en: "File another", mr: "आणखी एक नोंदवा", hi: "एक और दर्ज करें" },

  // ── operator ──
  "op.title": { en: "Operator console", mr: "कक्ष", hi: "ऑपरेटर कक्ष" },
  "op.sub": { en: "Reports stream in live. Register a found person to see AI-ranked matches.", mr: "नोंदी थेट येतात. जुळण्या पाहण्यासाठी सापडलेली व्यक्ती नोंदवा.", hi: "रिपोर्ट लाइव आती हैं. मिलान देखने के लिए मिला व्यक्ति दर्ज करें." },
  "op.booth": { en: "booth", mr: "बूथ", hi: "बूथ" },
  "op.registerFound": { en: "Register a found person", mr: "सापडलेली व्यक्ती नोंदवा", hi: "मिला व्यक्ति दर्ज करें" },
  "op.descReq": { en: "Description (clothes, appearance), required", mr: "वर्णन (कपडे, स्वरूप), आवश्यक", hi: "विवरण (कपड़े, रूप), आवश्यक" },
  "op.nameKnown": { en: "Name (if known)", mr: "नाव (माहित असल्यास)", hi: "नाम (यदि ज्ञात हो)" },
  "op.approxAge": { en: "Approx age", mr: "अंदाजे वय", hi: "अनुमानित आयु" },
  "op.language": { en: "Language", mr: "भाषा", hi: "भाषा" },
  "op.registerMatch": { en: "Register and find matches", mr: "नोंदवा आणि जुळवा", hi: "दर्ज करें और मिलान खोजें" },
  "op.searching": { en: "Searching", mr: "शोधत आहे", hi: "खोज रहे हैं" },
  "op.candidates": { en: "Candidates for found case", mr: "सापडलेल्या केससाठी उमेदवार", hi: "मिले केस के लिए उम्मीदवार" },
  "op.searchingGraph": { en: "Searching reports and validating against the venue graph.", mr: "नोंदी शोधत आहे व ठिकाण-आलेखाशी पडताळत आहे.", hi: "रिपोर्ट खोज रहे हैं और स्थल-ग्राफ़ से जाँच रहे हैं." },
  "op.confirmed": { en: "Match confirmed", mr: "जुळणी निश्चित", hi: "मिलान पुष्ट" },
  "op.reunionAt": { en: "Reunion at", mr: "भेट येथे", hi: "मिलन यहाँ" },
  "op.otpSent": { en: "An OTP SMS was sent to the family.", mr: "कुटुंबाला OTP एसएमएस पाठवला.", hi: "परिवार को OTP एसएमएस भेजा गया." },
  "op.otpNoKey": { en: "OTP generated. SMS sender not configured, see logs.", mr: "OTP तयार झाला. एसएमएस सेवा सेट नाही, लॉग पाहा.", hi: "OTP बना. एसएमएस सेवा सेट नहीं, लॉग देखें." },
  "op.confidence": { en: "confidence", mr: "विश्वास", hi: "विश्वास" },
  "op.vector": { en: "vector", mr: "व्हेक्टर", hi: "वेक्टर" },
  "op.confirm": { en: "Confirm match", mr: "जुळणी निश्चित करा", hi: "मिलान पुष्टि करें" },
  "op.rejectAll": { en: "None of these match, reject all", mr: "यांपैकी एकही जुळत नाही, सर्व नाकारा", hi: "इनमें कोई मेल नहीं, सभी अस्वीकार करें" },
  "op.noCandidates": { en: "No candidates above the confidence floor yet. The found report stays unmatched and will escalate on the normal timeline.", mr: "अद्याप विश्वास-मर्यादेवरील उमेदवार नाहीत. नोंद अजुळलेली राहते व नेहमीच्या वेळेनुसार पुढे जाते.", hi: "अभी विश्वास-सीमा से ऊपर कोई उम्मीदवार नहीं. रिपोर्ट बिना-मिलान रहती है और सामान्य समय पर एस्केलेट होगी." },
  "op.findMatches": { en: "Find matches", mr: "जुळणी शोधा", hi: "मिलान खोजें" },
  "op.blastZone": { en: "Blast this person's zone", mr: "या व्यक्तीची सूचना क्षेत्राला पाठवा", hi: "इस व्यक्ति के क्षेत्र में सूचना भेजें" },
  "op.blasting": { en: "Sending", mr: "पाठवत आहे", hi: "भेज रहे हैं" },
  "op.blasted": { en: "Alerted {n} recipients across {z} zones (incl. adjacent).", mr: "{z} क्षेत्रांतील {n} जणांना सूचना (शेजारीसह).", hi: "{z} क्षेत्रों के {n} लोगों को सूचना (निकटवर्ती सहित)." },
  "op.missingHint": { en: "This is a missing-person report, searchable the moment it landed. Register the matching found person above to surface it as a candidate.", mr: "ही हरवल्याची नोंद आहे, येताच शोधण्यायोग्य. उमेदवार म्हणून दिसण्यासाठी वर सापडलेली व्यक्ती नोंदवा.", hi: "यह लापता रिपोर्ट है, आते ही खोजने-योग्य. उम्मीदवार के रूप में दिखाने हेतु ऊपर मिला व्यक्ति दर्ज करें." },
  "op.age": { en: "Age", mr: "वय", hi: "आयु" },
  "op.from": { en: "From", mr: "मूळ गाव", hi: "मूल स्थान" },
  "op.contact": { en: "Contact", mr: "संपर्क", hi: "संपर्क" },
  "op.description": { en: "Description", mr: "वर्णन", hi: "विवरण" },
  "op.selectReport": { en: "Select a report to see details.", mr: "तपशील पाहण्यासाठी एक नोंद निवडा.", hi: "विवरण देखने के लिए एक रिपोर्ट चुनें." },
  "op.noChannel": { en: "No reports on this channel yet.", mr: "या माध्यमावर अद्याप नोंदी नाहीत.", hi: "इस माध्यम पर अभी रिपोर्ट नहीं." },

  // ── blast ──
  "bl.eyebrow": { en: "Escalation · location blast", mr: "तातडी · क्षेत्र सूचना", hi: "एस्केलेशन · क्षेत्र सूचना" },
  "bl.title": { en: "Alert a whole zone in one moment", mr: "संपूर्ण क्षेत्राला एका क्षणात सूचना", hi: "पूरे क्षेत्र को एक पल में सूचना" },
  "bl.sub": { en: "When a case stays open, NANDI reaches everyone opted in to a zone and its adjacent zones, across every channel at once. This is the same engine the 24h re-blast and 72h police escalation run on, here as a manual control.", mr: "केस उघडी राहिल्यास, नंदी क्षेत्रातील व शेजारील क्षेत्रांतील सर्व नोंदणीकृतांना सर्व माध्यमांतून एकाच वेळी संपर्क करते. हेच इंजिन २४ तास पुन्हा-सूचना व ७२ तास पोलिस तातडीसाठी चालते, येथे हाताळणीसाठी.", hi: "केस खुली रहने पर, नंदी क्षेत्र व निकटवर्ती क्षेत्रों के सभी पंजीकृत लोगों तक हर माध्यम से एक साथ पहुँचती है. यही इंजन 24घं री-ब्लास्ट व 72घं पुलिस एस्केलेशन चलाता है, यहाँ मैनुअल नियंत्रण के रूप में." },
  "bl.channels": { en: "Notification channels", mr: "सूचना माध्यमे", hi: "सूचना माध्यम" },
  "bl.ready": { en: "ready to send", mr: "पाठवण्यास तयार", hi: "भेजने को तैयार" },
  "bl.noKeys": { en: "no keys yet, sends are logged no-ops", mr: "अद्याप की नाहीत, पाठवणे फक्त लॉग होते", hi: "अभी की नहीं, भेजना केवल लॉग होता है" },
  "bl.live": { en: "live", mr: "थेट", hi: "लाइव" },
  "bl.noKey": { en: "no key", mr: "की नाही", hi: "की नहीं" },
  "bl.noKeyNote": { en: "With no channel keys, a blast still resolves every recipient and writes the audit trail, each send just logs instead of leaving your machine. Add a key (see the setup guide) and the chip turns saffron.", mr: "की नसताना, सूचना तरीही प्रत्येक प्राप्तकर्ता ठरवते व नोंद ठेवते, फक्त पाठवणे लॉग होते. की जोडा म्हणजे चिन्ह केशरी होते.", hi: "की न होने पर भी सूचना हर प्राप्तकर्ता तय करती है व ऑडिट लिखती है, भेजना केवल लॉग होता है. की जोड़ें तो चिप केसरी हो जाती है." },
  "bl.blastZone": { en: "Blast a zone", mr: "क्षेत्राला सूचना", hi: "क्षेत्र को सूचना" },
  "bl.reachable": { en: "reachable in this zone", mr: "या क्षेत्रात पोहोचण्याजोगे", hi: "इस क्षेत्र में पहुँच-योग्य" },
  "bl.targetZone": { en: "Target zone", mr: "लक्ष्य क्षेत्र", hi: "लक्ष्य क्षेत्र" },
  "bl.reachableShort": { en: "reachable", mr: "पोहोचण्याजोगे", hi: "पहुँच-योग्य" },
  "bl.adjacentNote": { en: "Adjacent zones are included automatically, so neighbours hear it too.", mr: "शेजारील क्षेत्रे आपोआप समाविष्ट, त्यामुळे शेजाऱ्यांनाही कळते.", hi: "निकटवर्ती क्षेत्र अपने-आप शामिल, ताकि पड़ोसी भी सुनें." },
  "bl.subject": { en: "Subject (email title)", mr: "विषय (ईमेल शीर्षक)", hi: "विषय (ईमेल शीर्षक)" },
  "bl.message": { en: "Message", mr: "संदेश", hi: "संदेश" },
  "bl.messagePlaceholder": { en: "e.g. a 7-year-old boy in a red t-shirt was found at Ramkund", mr: "उदा. लाल टी-शर्टमधील ७ वर्षांचा मुलगा रामकुंड येथे सापडला", hi: "उदा. लाल टी-शर्ट में 7 वर्षीय लड़का रामकुंड में मिला" },
  "bl.send": { en: "Blast", mr: "सूचना पाठवा", hi: "सूचना भेजें" },
  "bl.sending": { en: "Sending", mr: "पाठवत आहे", hi: "भेज रहे हैं" },
  "bl.dispatched": { en: "Blast dispatched", mr: "सूचना पाठवली", hi: "सूचना भेजी गई" },
  "bl.targeted": { en: "Targeted {n} recipients across {z} zones (incl. adjacent).", mr: "{z} क्षेत्रांतील {n} जणांना लक्ष्य (शेजारीसह).", hi: "{z} क्षेत्रों के {n} लोगों को लक्षित (निकटवर्ती सहित)." },
  "bl.noRecipients": { en: "No opted-in recipients in this zone yet. Add some on the right, then blast again.", mr: "या क्षेत्रात अद्याप नोंदणीकृत प्राप्तकर्ते नाहीत. उजवीकडे जोडा, मग पुन्हा पाठवा.", hi: "इस क्षेत्र में अभी पंजीकृत प्राप्तकर्ता नहीं. दाईं ओर जोड़ें, फिर भेजें." },
  "bl.sentOf": { en: "sent", mr: "पाठवले", hi: "भेजे" },
  "bl.subscribers": { en: "Subscribers", mr: "नोंदणीकृत", hi: "ग्राहक" },
  "bl.total": { en: "total", mr: "एकूण", hi: "कुल" },
  "bl.noZone": { en: "No zone", mr: "क्षेत्र नाही", hi: "कोई क्षेत्र नहीं" },
  "bl.addrEmail": { en: "email address", mr: "ईमेल पत्ता", hi: "ईमेल पता" },
  "bl.addrTelegram": { en: "telegram chat id", mr: "टेलिग्राम चॅट आयडी", hi: "टेलीग्राम चैट आईडी" },
  "bl.addrPhone": { en: "phone (+91…)", mr: "फोन (+91…)", hi: "फोन (+91…)" },
  "bl.nameOpt": { en: "name (optional)", mr: "नाव (पर्यायी)", hi: "नाम (वैकल्पिक)" },
  "bl.addSub": { en: "Add subscriber", mr: "नोंदणी जोडा", hi: "ग्राहक जोड़ें" },
  "bl.adding": { en: "Adding", mr: "जोडत आहे", hi: "जोड़ रहे हैं" },
  "bl.noSubs": { en: "No subscribers yet. Add one above, or let people opt in by messaging the Telegram or WhatsApp bot.", mr: "अद्याप नोंदणी नाही. वर जोडा, किंवा टेलिग्राम/व्हॉट्सअ‍ॅप बॉटला संदेश पाठवून लोक नोंदणी करू शकतात.", hi: "अभी कोई ग्राहक नहीं. ऊपर जोड़ें, या लोग टेलीग्राम/व्हाट्सएप बॉट को संदेश भेजकर जुड़ें." },
};

type Ctx = { lang: Lang; setLang: (l: Lang) => void };
const LangCtx = createContext<Ctx>({ lang: "en", setLang: () => {} });

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>(() => (localStorage.getItem("nandi_lang") as Lang) || "en");
  useEffect(() => {
    localStorage.setItem("nandi_lang", lang);
    document.documentElement.lang = lang;
  }, [lang]);
  return <LangCtx.Provider value={{ lang, setLang }}>{children}</LangCtx.Provider>;
}

export function useLang() {
  return useContext(LangCtx);
}

/** Returns tr(key, vars?) bound to the current language, falling back to English. */
export function useT() {
  const { lang } = useLang();
  return (key: string, vars?: Record<string, string | number>) => {
    const entry = D[key];
    let s = entry ? entry[lang] ?? entry.en : key;
    if (vars) for (const [k, v] of Object.entries(vars)) s = s.replace(`{${k}}`, String(v));
    return s;
  };
}

export function LanguageSwitcher() {
  const { lang, setLang } = useLang();
  return (
    <div className="flex items-center gap-1 rounded-full border border-[var(--color-line)] bg-white/80 p-0.5" role="group" aria-label="Language">
      {LANGS.map((l) => (
        <button
          key={l.code}
          onClick={() => setLang(l.code)}
          aria-pressed={lang === l.code}
          className={`rounded-full px-2.5 py-1 text-[12px] font-semibold transition ${
            lang === l.code ? "bg-[var(--color-ink)] text-white" : "text-[var(--color-ink-soft)] hover:text-[var(--color-ink)]"
          }`}
        >
          {l.label}
        </button>
      ))}
    </div>
  );
}
