import os
import re
import json
import joblib
import numpy as np
from typing import Dict, Any, List, Tuple, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
MODEL_DIR = os.path.join(BASE_DIR, "models", "chatbot")

class MultilingualNLPEngine:
    """
    AI Module 5: Multilingual NLP Emergency & Chatbot Engine
    Supports Kannada (kn), Hindi (hi), Tamil (ta), Telugu (te), and English (en).
    Features:
    - Supervised Indic Text Intent Classification (Calibrated SGD + Char-WB TF-IDF)
    - Multilingual Script & Transliteration Detection
    - Disaster/SOS Emergency Entity Extraction (People, Meals, Urgency, Location)
    - Actionable UI Decision Hooks (Emergency Dispatch, Donation Creation, Food Safety Scanner)
    - Native Culturally Nuanced Response Generation
    - Real-Time Live Status Synchronization
    """

    LANGUAGES = {
        "en": "English",
        "kn": "ಕನ್ನಡ (Kannada)",
        "hi": "हिन्दी (Hindi)",
        "ta": "தமிழ் (Tamil)",
        "te": "తెలుగు (Telugu)"
    }

    # Intent Classification Fallback Keywords (Multilingual Indic Lexicon)
    INTENT_PATTERNS = {
        "DONATION_INQUIRY": {
            "en": [r"donate", r"donation", r"give food", r"surplus", r"how to donate", r"contribute", r"excess food"],
            "kn": [r"ದಾನ", r"ಕೊಡು", r"ಆಹಾರ", r"ಊಟ", r"ಹೇಗೆ ದಾನ ಮಾಡುವುದು", r"ಹೆಚ್ಚುವರಿ ಆಹಾರ", r"ಅನ್ನದಾನ"],
            "hi": [r"दान", r"भोजन", r"खाना", r"अन्न", r"कैसे दान करें", r"अतिरिक्त भोजन", r"खाना देना"],
            "ta": [r"தானம்", r"உணவு", r"சாப்பாடு", r"கொடுக்க", r"எப்படி தானம் செய்வது", r"மீதமுள்ள உணவு"],
            "te": [r"దానం", r"ఆహారం", r"భోజనం", r"అన్నదానం", r"ఎలా దానం చేయాలి", r"మిగిలిన ఆహారం"]
        },
        "FOOD_SAFETY": {
            "en": [r"safety", r"safe", r"shelf life", r"spoil", r"mold", r"expiry", r"fssai", r"temperature", r"hot", r"cold", r"bacterial"],
            "kn": [r"ಸುರಕ್ಷತೆ", r"ಹಾಳಾಗು", r"ಕೆಡು", r"ತಾಜಾ", r"ಬೂಸ್ಟು", r"ತಾಪಮಾನ", r"ಎಫ್‌ಎಸ್‌ಎಸ್‌ಎಐ", r"ಶೆಲ್ಫ್ ಲೈಫ್"],
            "hi": [r"सुरक्षा", r"खराब", r"सड़ना", r"फफूंद", r"शेल्फ लाइफ", r"तापमान", r"एफएसएसएआई", r"ताजा"],
            "ta": [r"பாதுகாப்பு", r"கெட்டுப்போ", r"பூஞ்சை", r"வெப்பநிலை", r"எஃப்எஸ்எஸ்ஏஐ", r"புதிய"],
            "te": [r"భద్రత", r"పాడైపో", r"బూజు", r"షెల్ఫ్ లైఫ్", r"ఉష్ణోగ్రత", r"తాజా"]
        },
        "EMERGENCY_SOS": {
            "en": [r"emergency", r"sos", r"starving", r"hungry", r"flood", r"disaster", r"urgent food", r"need food now", r"immediate relief"],
            "kn": [r"ತುರ್ತು", r"ಹಸಿವು", r"ಸಂಕಷ್ಟ", r"ಪ್ರವಾಹ", r"ತಕ್ಷಣ ಆಹಾರ ಬೇಕು", r"ಆಪತ್ತು", r"ಎಸ್ಒಎಸ್", r"ವರದಗಳು"],
            "hi": [r"आपातकालीन", r"भूख", r"आपदा", r"बाढ़", r"तुरंत खाना चाहिए", r"संकट", r"एसओएस"],
            "ta": [r"அவசரம்", r"பசி", r"பேரிடர்", r"வெள்ளம்", r"உடனே உணவு வேண்டும்", r"எஸ்ஓஎஸ்"],
            "te": [r"అత్యవసర", r"ఆకలి", r"విపత్తు", r"వరదలు", r"వెంటనే ఆహారం కావాలి", r"ఎస్ఓఎస్"]
        },
        "VOLUNTEER_INQUIRY": {
            "en": [r"volunteer", r"deliver", r"pickup", r"driver", r"help out", r"join as volunteer", r"vehicle"],
            "kn": [r"ಸ್ವಯಂಸೇವಕ", r"ಸಹಾಯ", r"ಡೆಲಿವರಿ", r"ವಾಹನ", r"ಸೇರ್ಪಡೆ", r"ಸೇವಕ"],
            "hi": [r"स्वयंसेवक", r"मदद", r"डिलीवरी", r"पिकअप", r"स्वयंसेवा", r"जुड़ें"],
            "ta": [r"தன்னார்வலர்", r"உதவி", r"டெலிவரி", r"பிக்கப்", r"இணைய"],
            "te": [r"వాలంటీర్", r"సహాయం", r"డెಲಿవరీ", r"పికప్", r"చేరండి"]
        },
        "NGO_INQUIRY": {
            "en": [r"ngo", r"charity", r"orphanage", r"shelter", r"claim food", r"community kitchen"],
            "kn": [r"ಎನ್‌ಜಿಒ", r"ಸಂಸ್ಥೆ", r"ಅನಾಥಾಶ್ರಮ", r"ಆಶ್ರಮ", r"ಆಹಾರ ಪಡೆಯಲು"],
            "hi": [r"एनजीओ", r"संस्था", r"अनाथालय", r"आश्रम", r"भोजन प्राप्त करें"],
            "ta": [r"என்ஜிஓ", r"அறக்கட்டளை", r"ஆதரவற்றோர் இல்லம்", r"உணவு பெற"],
            "te": [r"ఎన్జీఓ", r"సంస్థ", r"అనాథాశ్రమం", r"ఆహారం పొందడానికి"]
        },
        "STATUS_TRACKING": {
            "en": [r"status", r"track", r"where is my", r"active donation", r"delivery tracking", r"delivery status"],
            "kn": [r"ಸ್ಥಿತಿ", r"ಟ್ರ್ಯಾಕ್", r"ನನ್ನ ದಾನ ಎಲ್ಲಿದೆ", r"ಡೆಲಿವರಿ ಸ್ಥಿತಿ"],
            "hi": [r"स्थिति", r"ट्रैक", r"मेरा दान कहां है", r"डिलीवरी स्थिति"],
            "ta": [r"நிலை", r"டிராக்", r"என் தானம் எங்கே", r"டெலிவரி நிலை"],
            "te": [r"స్థితి", r"ట్రాక్", r"నా దానం ఎక్కడ ఉంది", r"డెలివరీ స్థితి"]
        }
    }

    # Curated Knowledge Base Answers in all 5 Languages
    KNOWLEDGE_BASE = {
        "DONATION_INQUIRY": {
            "en": {
                "text": "To donate surplus food, go to your Donor Dashboard and click 'Add Donation'. You can snap a photo with our AI Scanner, specify cooked or raw food, quantity, and pickup location. A nearby verified NGO or volunteer will be dispatched immediately!",
                "followups": ["What foods are accepted?", "How is food packed?", "Track my donation status"]
            },
            "kn": {
                "text": "ಹೆಚ್ಚುವರಿ ಆಹಾರವನ್ನು ದಾನ ಮಾಡಲು, ನಿಮ್ಮ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್‌ನಲ್ಲಿ 'Add Donation' ಕ್ಲಿಕ್ ಮಾಡಿ. ನಮ್ಮ AI ಸ್ಕ್ಯಾನರ್ ಮೂಲಕ ಫೋಟೋ ತೆಗೆದು, ಆಹಾರದ ವಿಧ ಮತ್ತು ಪ್ರಮಾಣವನ್ನು ನಮೂದಿಸಿ. ಹತ್ತಿರದ ಪರಿಶೀಲಿಸಿದ ಎನ್‌ಜಿಒ ಅಥವಾ ಸ್ವಯಂಸೇವಕರು ತಕ್ಷಣವೇ ಬಂದು ಆಹಾರವನ್ನು ಸಂಗ್ರಹಿಸುತ್ತಾರೆ!",
                "followups": ["ಯಾವ ಆಹಾರವನ್ನು ಸ್ವೀಕರಿಸಲಾಗುತ್ತದೆ?", "ಪ್ಯಾಕೇಜಿಂಗ್ ನಿಯಮಗಳೇನು?", "ನನ್ನ ದಾನವನ್ನು ಟ್ರ್ಯಾಕ್ ಮಾಡಿ"]
            },
            "hi": {
                "text": "अतिरिक्त भोजन दान करने के लिए, अपने डैशबोर्ड पर 'Add Donation' पर क्लिक करें। हमारे AI स्कैनर से फोटो लें, भोजन का प्रकार और मात्रा दर्ज करें। नजदीकी सत्यापित एनजीओ या स्वयंसेवक तुरंत भोजन लेने पहुंचेंगे!",
                "followups": ["कौन सा भोजन स्वीकार्य है?", "पैकेजिंग के नियम क्या हैं?", "दान की स्थिति देखें"]
            },
            "ta": {
                "text": "மீதமுள்ள உணவை தானம் செய்ய, உங்கள் டாஷ்போர்டில் 'Add Donation' என்பதைக் கிளிக் செய்யவும். AI ஸ்கேனர் மூலம் புகைப்படம் எடுத்து, உணவின் விவரங்கள் மற்றும் அளவை உள்ளிடவும். அருகிலுள்ள சரிபார்க்கப்பட்ட என்ஜிஓ உடனடியாக வந்து உணவை பெற்றுக்கொள்ளும்!",
                "followups": ["எந்த உணவுகள் ஏற்கப்படும்?", "பேக்கேஜிங் விதிகள் என்ன?", "என் தானத்தை கண்காணிக்கவும்"]
            },
            "te": {
                "text": "మిగిలిన ఆహారాన్ని దానం చేయడానికి, మీ డ్యాష్‌బోర్డ్‌లో 'Add Donation' క్లిక్ చేయండి. మా AI స్కానర్ ద్వారా ఫోటో తీసి, ఆహార రకం మరియు పరిమాణాన్ని నమోదు చేయండి. సమీపంలోని ఎన్జీఓ లేదా వాలంటీర్ వెంటనే వచ్చి ఆహారాన్ని సేకరిస్తారు!",
                "followups": ["ఏ ఆహారాలు ఆమోదించబడతాయి?", "ప్యాకేజింగ్ నిబంధనలు ఏమిటి?", "నా దానం ట్రాక్ చేయండి"]
            }
        },
        "FOOD_SAFETY": {
            "en": {
                "text": "Under FSSAI Schedule 4 and FoodBridge Safety Standards, cooked food kept at room temperature (25°C - 35°C) must be redistributed within 4 hours. Keep food in airtight stainless steel or sealed food-grade containers. Our AI Shelf-Life Predictor automatically monitors safe consumption windows.",
                "followups": ["How does AI test freshness?", "Safe storage containers", "Report spoiled food"]
            },
            "kn": {
                "text": "FSSAI ಮತ್ತು ಫುಡ್‌ಬ್ರಿಡ್ಜ್ ಸುರಕ್ಷತಾ ನಿಯಮಗಳ ಪ್ರಕಾರ, ಕೋಣೆಯ ತಾಪಮಾನದಲ್ಲಿ ಬೇಯಿಸಿದ ಆಹಾರವನ್ನು 4 ಗಂಟೆಗಳ ಒಳಗೆ ವಿತರಿಸಬೇಕು. ಆಹಾರವನ್ನು ಗಾಳಿಯಾಡದ ಸ್ಟೇನ್‌ಲೆಸ್ ಸ್ಟೀಲ್ ಅಥವಾ ಸೀಲ್ ಮಾಡಿದ ಕಂಟೈನರ್‌ಗಳಲ್ಲಿ ಇರಿಸಿ. ನಮ್ಮ AI ಶೆಲ್ಫ್-ಲೈಫ್ ಪ್ರಿಡಿಕ್ಟರ್ ಸುರಕ್ಷಿತ ಸಮಯವನ್ನು ಸ್ವಯಂಚಾಲಿತವಾಗಿ ಲೆಕ್ಕಾಚಾರ ಮಾಡುತ್ತದೆ.",
                "followups": ["AI ತಾಜಾತನವನ್ನು ಹೇಗೆ ಪರಿಶೀಲಿಸುತ್ತದೆ?", "ಉತ್ತಮ ಕಂಟೈನರ್‌ಗಳು ಯಾವುವು?", "ಹಾಳಾದ ಆಹಾರ ವರದಿ ಮಾಡಿ"]
            },
            "hi": {
                "text": "FSSAI अनुसूची 4 और फ़ूडब्रिज सुरक्षा नियमों के अनुसार, कमरे के तापमान पर पके हुए भोजन को 4 घंटे के भीतर वितरित किया जाना चाहिए। भोजन को एयरटाइट स्टील या सीलबंद कंटेनर में रखें। हमारा AI शेल्फ-लाइफ प्रिडिक्टर सुरक्षित समय की स्वतः गणना करता है।",
                "followups": ["AI ताजगी की जांच कैसे करता है?", "सुरक्षित कंटेनर कौन से हैं?", "खराब भोजन की सूचना दें"]
            },
            "ta": {
                "text": "FSSAI மற்றும் ஃபுட்பிரிட்ஜ் பாதுகாப்பு விதிகளின்படி, அறை வெப்பநிலையில் சமைத்த உணவை 4 மணி நேரத்திற்குள் விநியோகிக்க வேண்டும். உணவை காற்று புகாத பாத்திரங்களில் மூடி வைக்கவும். எங்கள் AI ஷெல்ஃப்-லைஃப் காலக்கெடுவை துல்லியமாக கணக்கிடுகிறது.",
                "followups": ["AI தரத்தை எவ்வாறு சரிபார்க்கிறது?", "பாதுகாப்பான கொள்கலன்கள்", "கெட்ட உணவு புகார்"]
            },
            "te": {
                "text": "FSSAI మరియు ఫుడ్‌బ్రిడ్జ్ భద్రతా ప్రమాణాల ప్రకారం, గది ఉష్ణోగ్రత వద్ద వండిన ఆహారాన్ని 4 గంటలలోపు పంపిణీ చేయాలి. ఆహారాన్ని ఎయిర్‌టైట్ కంటైనర్‌లలో భద్రపరచండి. మా AI షెల్ఫ్-లైఫ్ ప్రిడిక్టర్ సురక్షిత వినియోగ సమయాన్ని లెక్కిస్తుంది.",
                "followups": ["AI తాజాదనాన్ని ఎలా తనిఖీ చేస్తుంది?", "సురక్షిత కంటైనర్లు", "పాడైన ఆహారాన్ని నివేదించండి"]
            }
        },
        "EMERGENCY_SOS": {
            "en": {
                "text": "🚨 Emergency Distress Alert Triggered. If your shelter, community, or flood relief area needs immediate food supply, relief coordinators will immediately dispatch high-priority ready-to-eat ration packs and cooked meals within 45-60 minutes.",
                "followups": ["Raise Emergency Request", "Call Helpline 1800-FOOD-BRIDGE", "Nearby Relief Centers"]
            },
            "kn": {
                "text": "🚨 ತುರ್ತು ಪರಿಸ್ಥಿತಿ ಎಚ್ಚರಿಕೆ ಸಕ್ರಿಯಗೊಂಡಿದೆ. ನಿಮ್ಮ ಆಶ್ರಮ ಅಥವಾ ಪ್ರವಾಹ ಪೀಡಿತ ಪ್ರದೇಶಕ್ಕೆ ತುರ್ತು ಆಹಾರದ ಅಗತ್ಯವಿದ್ದರೆ, ಪರಿಹಾರ ತಂಡವು 45-60 ನಿಮಿಷಗಳಲ್ಲಿ ಹೆಚ್ಚಿನ ಆದ್ಯತೆಯ ಊಟದ ಪ್ಯಾಕೆಟ್‌ಗಳನ್ನು ತಲುಪಿಸುತ್ತದೆ.",
                "followups": ["ತುರ್ತು ಮನವಿ ಸಲ್ಲಿಸಿ", "ಸಹಾಯವಾಣಿ: 1800-FOOD-BRIDGE", "ಹತ್ತಿರದ ಪರಿಹಾರ ಕೇಂದ್ರಗಳು"]
            },
            "hi": {
                "text": "🚨 आपातकालीन संकट अलर्ट सक्रिय। यदि आपके आश्रय या बाढ़ राहत क्षेत्र को तुरंत भोजन की आवश्यकता है, तो राहत समन्वयक 45-60 मिनट के भीतर उच्च प्राथमिकता वाले भोजन पैकेट पहुंचाएंगे।",
                "followups": ["आपातकालीन अनुरोध दर्ज करें", "हेल्पलाइन: 1800-FOOD-BRIDGE", "राहत केंद्र"]
            },
            "ta": {
                "text": "🚨 அவசர உதவி எச்சரிக்கை இயக்கப்பட்டது. உங்கள் பகுதிக்கு உடனடி உணவு தேவைப்பட்டால், நிவாரண குழுவினர் 45-60 நிமிடங்களில் முன்னுரிமையுடன் உணவை விநியோகிப்பார்கள்.",
                "followups": ["அவசர கோரிக்கை வைக்கவும்", "ஹெல்ப்லைன்: 1800-FOOD-BRIDGE", "அருகிலுள்ள நிவாரண முகாம்கள்"]
            },
            "te": {
                "text": "🚨 అత్యవసర సహాయ అలర్ట్ యాక్టివ్ చేయబడింది. మీ ప్రాంతానికి వెంటనే ఆహారం కావాలంటే, సహాయక బృందం 45-60 నిమిషాలలోపు ఆహార ప్యాకెట్లను సరఫరా చేస్తుంది.",
                "followups": ["అత్యవసర అభ్యర్థన సమర్పించండి", "హెల్ప్‌లైన్: 1800-FOOD-BRIDGE", "సహాయ కేంద్రాలు"]
            }
        },
        "VOLUNTEER_INQUIRY": {
            "en": {
                "text": "Volunteers are the backbone of FoodBridge! You can sign up with a bike, scooter, or van to accept nearby food transport tasks. Each pickup includes live navigation, contact details, and secure OTP confirmation upon handover.",
                "followups": ["How to sign up?", "Vehicle requirements", "View available tasks"]
            },
            "kn": {
                "text": "ಸ್ವಯಂಸೇವಕರು ಫುಡ್‌ಬ್ರಿಡ್ಜ್‌ನ ಬೆನ್ನೆಲುಬು! ಹತ್ತಿರದ ಆಹಾರ ಸಾಗಣೆ ಕಾರ್ಯಗಳನ್ನು ಸ್ವೀಕರಿಸಲು ನೀವು ಬೈಕ್, ಸ್ಕೂಟರ್ ಅಥವಾ ವ್ಯಾನ್‌ನೊಂದಿಗೆ ನೋಂದಾಯಿಸಿಕೊಳ್ಳಬಹುದು. ಪ್ರತಿ ಪಿಕಪ್‌ನಲ್ಲಿ ಲೈವ್ ಮ್ಯಾಪ್ ಮತ್ತು OTP ದೃಢೀಕರಣವಿರುತ್ತದೆ.",
                "followups": ["ಸ್ವಯಂಸೇವಕರಾಗಿ ಸೇರುವುದು ಹೇಗೆ?", "ವಾಹನ ನಿಯಮಗಳು", "ಲಭ್ಯವಿರುವ ಕಾರ್ಯಗಳು"]
            },
            "hi": {
                "text": "स्वयंसेवक फ़ूडब्रिज की रीढ़ हैं! नजदीकी भोजन वितरण कार्यों को स्वीकार करने के लिए आप बाइक, स्कूटर या वैन के साथ पंजीकरण कर सकते हैं। प्रत्येक पिकअप में लाइव नेविगेशन और सुरक्षित ओटीपी शामिल है।",
                "followups": ["पंजीकरण कैसे करें?", "वाहन आवश्यकताएं", "उपलब्ध कार्य देखें"]
            },
            "ta": {
                "text": "தன்னார்வலர்கள் ஃபுட்பிரிட்ஜின் முக்கிய தூண்கள்! அருகிலுள்ள உணவு விநியோக பணிகளை ஏற்க நீங்கள் பைக் அல்லது வேனுடன் பதிவு செய்யலாம். ஒவ்வொரு பிக்கப்பிற்கும் நேரடி வரைபடம் மற்றும் ஓடிபி சரிபார்ப்பு உண்டு.",
                "followups": ["எப்படி இணைவது?", "வாகன தகுதிகள்", "கிடைக்கும் பணிகளைப் பார்க்கவும்"]
            },
            "te": {
                "text": "వాలంటీర్లు ఫుడ్‌బ్రిడ్జ్ యొక్క వెన్నెముక! సమీపంలోని ఆహార రవాణా పనులను స్వీకరించడానికి మీరు బైక్ లేదా వ్యాన్‌తో నమోదు చేసుకోవచ్చు. ప్రతి పికప్‌కు లైవ్ నావిగేషన్ మరియు సురక్షిత OTP ఉంటుంది.",
                "followups": ["ఎలా చేరాలి?", "వాహన అర్హతలు", "అందుబాటులో ఉన్న పనులు"]
            }
        },
        "NGO_INQUIRY": {
            "en": {
                "text": "Verified charities, orphanages, and relief shelters can claim large-scale bulk donations completely free of charge. Submit your registration certificate and 80G documents in the Receiver Portal for 24-hour verification.",
                "followups": ["NGO Registration steps", "Claim guidelines", "Contact Admin"]
            },
            "kn": {
                "text": "ಪರಿಶೀಲಿಸಿದ ಅನಾಥಾಶ್ರಮಗಳು ಮತ್ತು ಸೇವಾ ಸಂಸ್ಥೆಗಳು ಉಚಿತವಾಗಿ ದೊಡ್ಡ ಪ್ರಮಾಣದ ಆಹಾರ ದಾನಗಳನ್ನು ಪಡೆಯಬಹುದು. 24 ಗಂಟೆಗಳ ಪರಿಶೀಲನೆಗಾಗಿ ರಿಸೀವರ್ ಪೋರ್ಟಲ್‌ನಲ್ಲಿ ನಿಮ್ಮ ನೋಂದಣಿ ಪ್ರಮಾಣಪತ್ರವನ್ನು ಸಲ್ಲಿಸಿ.",
                "followups": ["ಎನ್‌ಜಿಒ ನೋಂದಣಿ ಕ್ರಮಗಳು", "ಆಹಾರ ಪಡೆಯುವ ನಿಯಮಗಳು", "ಅಡ್ಮಿನ್ ಸಂಪರ್ಕಿಸಿ"]
            },
            "hi": {
                "text": "सत्यापित अनाथालय और गैर-सरकारी संगठन बिल्कुल मुफ्त में बड़े पैमाने पर भोजन दान प्राप्त कर सकते हैं। 24 घंटे के सत्यापन के लिए रिसीवर पोर्टल पर अपना पंजीकरण प्रमाण पत्र जमा करें।",
                "followups": ["एनजीओ पंजीकरण प्रक्रिया", "भोजन प्राप्त करने के नियम", "एडमिन से संपर्क करें"]
            },
            "ta": {
                "text": "அங்கீகரிக்கப்பட்ட தொண்டு நிறுவனங்கள் மற்றும் ஆதரவற்றோர் இல்லங்கள் முற்றிலும் இலவசமாக மொத்த உணவு தானங்களைப் பெறலாம். 24 மணி நேர சரிபார்ப்புக்கு உங்கள் சான்றிதழை பதிவேற்றவும்.",
                "followups": ["என்ஜிஓ பதிவு முறைகள்", "உணவு பெறும் விதிகள்", "நிர்வாகியைத் தொடர்பு கொள்ளவும்"]
            },
            "te": {
                "text": "ధృవీకరించబడిన స్వచ్ఛంద సంస్థలు మరియు అనాథాశ్రమాలు పూర్తిగా ఉచితంగా ఆహార ದಾನాలను పొందవచ్చు. 24 గంటల ధృవీకరణ కోసం మీ రిజిస్ట్రేషన్ సర్టిఫికేట్‌ను సమర్పించండి.",
                "followups": ["ఎన్జీఓ నమోదు దశలు", "నిబంధనలు", "అడ్మిన్‌ను సంప్రదించండి"]
            }
        },
        "STATUS_TRACKING": {
            "en": {
                "text": "To check your live donation or delivery status, visit the 'Donations' or 'Tasks' tab. All dispatches feature real-time GPS tracking and instant status timestamps.",
                "followups": ["Live GPS tracking", "Contact assigned volunteer", "Download delivery receipt"]
            },
            "kn": {
                "text": "ನಿಮ್ಮ ಸಕ್ರಿಯ ದಾನ ಅಥವಾ ಡೆಲಿವರಿ ಸ್ಥಿತಿಯನ್ನು ಪರಿಶೀಲಿಸಲು, 'Donations' ಅಥವಾ 'Tasks' ಟ್ಯಾಬ್‌ಗೆ ಭೇಟಿ ನೀಡಿ. ಎಲ್ಲಾ ವಿತರಣೆಗಳು ಲೈವ್ ಜಿಪಿಎಸ್ ಟ್ರ್ಯಾಕಿಂಗ್ ಹೊಂದಿರುತ್ತವೆ.",
                "followups": ["ಲೈವ್ ಜಿಪಿಎಸ್ ಟ್ರ್ಯಾಕಿಂಗ್", "ನಿಯೋಜಿತ ಸ್ವಯಂಸೇವಕರನ್ನು ಸಂಪರ್ಕಿಸಿ", "ರಶೀದಿ ಡೌನ್‌ಲೋಡ್"]
            },
            "hi": {
                "text": "अपने दान या डिलीवरी की लाइव स्थिति जांचने के लिए, 'Donations' या 'Tasks' टैब पर जाएं। सभी डिलीवरी में लाइव जीपीएस ट्रैकिंग की सुविधा है।",
                "followups": ["लाइव जीपीएस ट्रैकिंग", "स्वयंसेवक से संपर्क करें", "रसीद डाउनलोड करें"]
            },
            "ta": {
                "text": "உங்கள் நேரடி தானம் அல்லது டெலிவரி நிலையை அறிய 'Donations' அல்லது 'Tasks' பகுதிக்குச் செல்லவும். நேரடி ஜிபிஎஸ் வசதி உள்ளது.",
                "followups": ["நேரடி ஜிபிஎஸ் கண்காணிப்பு", "தன்னார்வலரைத் தொடர்பு கொள்ளவும்", "ரசீது பதிவிறக்கம்"]
            },
            "te": {
                "text": "మీ లైవ్ దానం లేదా డెలివరీ స్థితిని తనిఖీ చేయడానికి, 'Donations' లేదా 'Tasks' ట్యాబ్‌ను సందర్శించండి. అన్ని డెలివరీలు రియల్ టైమ్ జీపీఎస్ ట్రాకింగ్ కలిగి ఉంటాయి.",
                "followups": ["లైవ్ జీపీఎస్ ట్రాకింగ్", "వాలంటీర్‌ను సంప్రదించండి", "రసీదు డౌన్‌లోడ్"]
            }
        },
        "GREETING_HELP": {
            "en": {
                "text": "Hello! I am the FoodBridge Multilingual AI Assistant. I can help you in English, Kannada (ಕನ್ನಡ), Hindi (हिन्दी), Tamil (தமிழ்), and Telugu (తెలుగు). How can I assist you today?",
                "followups": ["🍲 How to donate food?", "⏰ FSSAI 4-hour safety rules", "🚨 Emergency food SOS", "🤝 Become a volunteer"]
            },
            "kn": {
                "text": "ನಮಸ್ಕಾರ! ನಾನು ಫುಡ್‌ಬ್ರಿಡ್ಜ್ ಬಹುಭಾಷಾ AI ಸಹಾಯಕ. ನಾನು ಕನ್ನಡ, ಇಂಗ್ಲಿಷ್, ಹಿಂದಿ, ತಮಿಳು ಮತ್ತು ತೆಲುಗು ಭಾಷೆಗಳಲ್ಲಿ ನಿಮಗೆ ಸಹಾಯ ಮಾಡಬಲ್ಲೆ. ಇಂದು ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಲಿ?",
                "followups": ["🍲 ಆಹಾರ ದಾನ ಮಾಡುವುದು ಹೇಗೆ?", "⏰ ಆಹಾರ ಸುರಕ್ಷತಾ ನಿಯಮಗಳು", "🚨 ತುರ್ತು ಆಹಾರ ಸಹಾಯ", "🤝 ಸ್ವಯಂಸೇವಕರಾಗಿ"]
            },
            "hi": {
                "text": "नमस्ते! मैं फ़ूडब्रिज बहुभाषी AI सहायक हूँ। मैं हिन्दी, अंग्रेजी, कन्नड़, तमिल और तेलुगु में आपकी सहायता कर सकता हूँ। आज मैं आपकी क्या मदद कर सकता हूँ?",
                "followups": ["🍲 भोजन दान कैसे करें?", "⏰ खाद्य सुरक्षा नियम", "🚨 आपातकालीन सहायता", "🤝 स्वयंसेवक बनें"]
            },
            "ta": {
                "text": "வணக்கம்! நான் ஃபுட்பிரிட்ஜ் பலமொழி AI உதவியாளர். தமிழ், ஆங்கிலம், கன்னடம், இந்தி மற்றும் தெலுங்கு மொழிகளில் உங்களுக்கு உதவ முடியும். இன்று உங்களுக்கு எவ்வாறு உதவட்டும்?",
                "followups": ["🍲 உணவு தானம் செய்வது எப்படி?", "⏰ உணவு பாதுகாப்பு விதிகள்", "🚨 அவசர உணவு உதவி", "🤝 தன்னார்வலராக இணைய"]
            },
            "te": {
                "text": "నమస్కారం! నేను ఫుడ్‌బ్రిడ్జ్ బహుభాషా AI సహాయకుడిని. తెలుగు, ఇంగ్లీష్, కన్నడ, హిందీ మరియు తమిళ భాషలలో మీకు సహాయం చేయగలను. ఈరోజు మీకు ఎలా సహాయపడగలను?",
                "followups": ["🍲 ఆహారం ఎలా దానం చేయాలి?", "⏰ ఆహార భద్రత నియమాలు", "🚨 అత్యవసర ఆహార సహాయం", "🤝 వాలంటీర్‌గా చేరండి"]
            }
        }
    }

    def __init__(self):
        self.pipeline = None
        self.metrics = None
        self._load_pipeline()

    def _load_pipeline(self):
        """Loads serialized scikit-learn pipeline and metrics."""
        model_path = os.path.join(MODEL_DIR, "nlp_intent_model.joblib")
        metrics_path = os.path.join(MODEL_DIR, "model_metrics.json")
        try:
            if os.path.exists(model_path):
                self.pipeline = joblib.load(model_path)
            if os.path.exists(metrics_path):
                with open(metrics_path, "r", encoding="utf-8") as f:
                    self.metrics = json.load(f)
        except Exception as e:
            print(f"[MultilingualNLPEngine] Model load warning: {e}. Utilizing native rule-matcher.")

    @classmethod
    def detect_language(cls, text: str) -> str:
        """
        Detects language using Unicode script block analysis & Indic transliteration tokens.
        """
        if not text:
            return "en"

        counts = {
            "kn": len(re.findall(r'[\u0C80-\u0CFF]', text)),  # Kannada Unicode Block
            "hi": len(re.findall(r'[\u0900-\u097F]', text)),  # Devanagari / Hindi
            "ta": len(re.findall(r'[\u0B80-\u0BFF]', text)),  # Tamil
            "te": len(re.findall(r'[\u0C00-\u0C7F]', text)),  # Telugu
        }

        # Check if any Indic script dominates
        max_lang = max(counts, key=counts.get)
        if counts[max_lang] >= 2:
            return max_lang

        # Romanized / Transliterated keyword scoring
        lower = text.lower()
        translit_keywords = {
            "kn": ["oota", "oonu", "namaskara", "hege", "sahaya", "aahara", "beku", "maduvudu", "dharani"],
            "hi": ["namaste", "khana", "bhojan", "madad", "kripya", "chahiye", "kaise", "karein", "batao"],
            "ta": ["vanakkam", "sappadu", "unavu", "udavi", "eppadi", "vendum", "romba", "nandri"],
            "te": ["namaskaram", "bhojanam", "sahayam", "kavali", "ela", "cheyali", "dhanyavadalu"]
        }

        # Calculate word-boundary matches
        translit_scores = {
            lang: sum(1 for kw in kws if re.search(rf'\b{kw}\b', lower))
            for lang, kws in translit_keywords.items()
        }

        best_translit = max(translit_scores, key=translit_scores.get)
        if translit_scores[best_translit] > 0:
            return best_translit

        return "en"

    def classify_intent(self, message: str, lang: str = "en") -> Tuple[str, float]:
        """
        Predicts intent and calibrated confidence using ML pipeline with rule-based safety fallback.
        """
        lower = message.lower().strip()

        # 1. Security guardrail: refuse account deletion or credential manipulation
        if any(w in lower for w in ["delete account", "cancel account", "hack", "password reset", "ban user"]):
            return ("UNAUTHORIZED_ACTION", 0.99)

        # 2. Greeting check
        if any(w in lower for w in ["hi", "hello", "hey", "namaskara", "namaste", "vanakkam", "namaskaram", "help", "who are you"]):
            return ("GREETING_HELP", 0.96)

        # 3. Supervised Machine Learning Inference
        if self.pipeline:
            try:
                pred = self.pipeline.predict([message])[0]
                probs = self.pipeline.predict_proba([message])[0]
                idx = list(self.pipeline.classes_).index(pred)
                confidence = float(probs[idx])
                if confidence >= 0.40:
                    return (pred, confidence)
            except Exception:
                pass

        # 4. Lexicon Rule Fallback
        for intent, lang_dict in self.INTENT_PATTERNS.items():
            patterns = lang_dict.get(lang, []) + lang_dict.get("en", [])
            for pattern in patterns:
                if re.search(pattern, message, re.IGNORECASE):
                    return (intent, 0.92)

        return ("GENERAL_INQUIRY", 0.70)

    @classmethod
    def extract_entities(cls, text: str) -> Dict[str, Any]:
        """
        Extracts structured emergency or donation entities from natural language text:
        - quantity
        - number_of_people
        - food_type
        - urgency
        - location
        - disaster_type
        """
        msg = text.lower()
        
        # 1. Extract Quantity & People Count
        numbers = [int(s) for s in re.findall(r'\b\d+\b', msg)]
        quantity = 0
        people = 0

        # Pattern: "for X people" or "X persons"
        people_match = re.search(r'(\d+)\s*(?:[a-zA-Z]+\s+)?(people|persons|folks|kids|victims|survivors|families|ಸಂತ್ರಸ್ತರಿಗೆ|ಜನರಿಗೆ|लोगों|பேர்|మంది)', msg)
        if people_match:
            people = int(people_match.group(1))

        # Pattern: "X meals/packets/kg/boxes" (allowing optional adjective e.g. "food packets")
        qty_match = re.search(r'(\d+)\s*(?:[a-zA-Z]+\s+)?(meals|packets|plates|boxes|kg|liters|packs|ration|bottles|ಊಟ|ಪೊಟ್ಟಣ|भोजन|पैकेट|பொட்டலம்|భోజనాలు)', msg)
        if qty_match:
            quantity = int(qty_match.group(1))

        # Numeric fallback if one was matched and other is missing
        if quantity == 0 and len(numbers) > 0:
            for n in numbers:
                if n != people:
                    quantity = n
                    break

        if people == 0 and len(numbers) > 0:
            for n in numbers:
                if n != quantity:
                    people = n
                    break

        # 2. Extract Food Category
        food_type = "Assorted Cooked Meals"
        if any(w in msg for w in ["water", "bottles", "ನೀರು", "पानी", "தண்ணீர்", "నీరు"]):
            food_type = "Water Bottles"
        elif any(w in msg for w in ["rice", "curry", "sambar", "ಅನ್ನ", "चावल", "சாதம்", "అన్నం"]):
            food_type = "Rice & Curry Meals"
        elif any(w in msg for w in ["bread", "bakery", "roti", "chapati", "ಬ್ರೆಡ್", "रोटी", "ரொட்டி"]):
            food_type = "Bread & Bakery"
        elif any(w in msg for w in ["ration", "grocery", "dhal", "ದಿನಸಿ", "राशन", "மளிகை", "సరుకులు"]):
            food_type = "Dry Groceries & Rations"
        elif any(w in msg for w in ["fruit", "vegetable", "ಹಣ್ಣು", "ತರಕಾರಿ", "फल", "सब्जी", "காய்கறி", "కూరగాయలు"]):
            food_type = "Fresh Produce"

        # 3. Extract Urgency
        urgency = "MEDIUM"
        if any(w in msg for w in [
            "immediately", "urgent", "critical", "now", "sos", "starving", "emergency",
            "ತಕ್ಷಣ", "ತುರ್ತಾಗಿ", "ತುರ್ತು", "ಆಪತ್ತು",
            "तुरंत", "आपातकालीन", "आपात", "संकट",
            "உடனே", "அவசரம்", "அவசரமாக", "ஆபத்து",
            "వెంటనే", "అత్యవసర", "ఆపద"
        ]):
            urgency = "CRITICAL"
        elif any(w in msg for w in ["today", "soon", "quick", "ಆದಷ್ಟು ಬೇಗ", "जल्दी", "விரைவில்", "త్వరగా"]):
            urgency = "HIGH"

        # 4. Extract Disaster Type
        disaster = "Community Relief"
        if any(w in msg for w in ["flood", "waterlogging", "ಪ್ರವಾಹ", "बाढ़", "வெள்ளம்", "వరదలు"]):
            disaster = "Flood Relief"
        elif any(w in msg for w in ["fire", "blaze", "ಬೆಂಕಿ", "आग", "தீ", "అగ్ని"]):
            disaster = "Fire Relief"
        elif any(w in msg for w in ["drought", "dry", "ಬರಗಾಲ", "सूखा", "வறட்சி", "కరువు"]):
            disaster = "Drought Relief"
        elif any(w in msg for w in ["earthquake", "ഭൂകമ്പം", "ಭೂಕಂಪ", "भूकंप", "நிலநடுக்கம்", "భూకంపం"]):
            disaster = "Earthquake Relief"

        # 5. Extract City / Town / District Landmark with priority on exact local matches
        location = "Local Community"
        cities_map = [
            ("Maddur", ["maddur", "ಮದ್ದೂರು", "maddur town", "maddur station"]),
            ("Mandya", ["mandya", "ಮಂಡ್ಯ", "mandya city", "mandya rural"]),
            ("Srirangapatna", ["srirangapatna", "ಶ್ರೀರಂಗಪಟ್ಟಣ"]),
            ("Pandavapura", ["pandavapura", "ಪಾಂಡವಪುರ"]),
            ("Malavalli", ["malavalli", "ಮಳವಳ್ಳಿ"]),
            ("Ramanagara", ["ramanagara", "ರಾಮನಗರ"]),
            ("Channapatna", ["channapatna", "ಚನ್ನಪಟ್ಟಣ"]),
            ("Mysuru", ["mysuru", "mysore", "ಮೈಸೂರು"]),
            ("Nanjangud", ["nanjangud", "ನಂಜನಗೂಡು"]),
            ("Hassan", ["hassan", "ಹಾಸನ"]),
            ("Tumakuru", ["tumakuru", "tumkur", "ತುಮಕೂರು"]),
            ("Bangalore Central", ["bangalore", "bengaluru", "ಬೆಂಗಳೂರು", "mg road", "central"]),
            ("Indiranagar", ["indiranagar", "ಇಂದಿರಾನಗರ"]),
            ("Koramangala", ["koramangala", "ಕೋರಮಂಗಲ"]),
            ("Whitefield", ["whitefield"]),
            ("Agrahara Circle", ["agrahara", "ಅಗ್ರಹಾರ", "mahasabha", "ಮಹಾಸಭಾ"]),
            ("Chennai", ["chennai", "சென்னை"]),
            ("Hyderabad", ["hyderabad", "హైదరాబాద్"]),
            ("Mumbai", ["mumbai", "मुंबई"]),
            ("Pune", ["pune", "पुणे"]),
            ("Delhi", ["delhi", "दिल्ली"]),
        ]
        for canonical, aliases in cities_map:
            if any(alias in msg for alias in aliases):
                location = canonical
                break

        # Distinguish quantity (meals) from number of people affected
        resolved_quantity = quantity if quantity > 0 else (people if people > 0 else 50)
        resolved_people = people if people > 0 else (max(1, int(quantity * 0.75)) if quantity > 0 else 30)

        return {
            "quantity": resolved_quantity,
            "number_of_people": resolved_people,
            "people_affected": resolved_people,
            "food_type": food_type,
            "urgency": urgency,
            "disaster_type": disaster,
            "location": location
        }

    def generate_response(
        self,
        message: str,
        preferred_language: str = "auto"
    ) -> Dict[str, Any]:
        """
        Generates contextual multilingual response, translation, entity extraction, and actionable follow-ups.
        """
        # 1. Determine Language
        detected_lang = self.detect_language(message)
        lang = detected_lang if preferred_language == "auto" else preferred_language
        if lang not in self.LANGUAGES:
            lang = "en"

        # 2. Classify Intent
        intent, confidence = self.classify_intent(message, lang)

        # 3. Extract Entities if relevant
        extracted_entities = None
        suggested_action = None
        if intent == "EMERGENCY_SOS":
            extracted_entities = self.extract_entities(message)
            suggested_action = "CREATE_EMERGENCY_REQUEST"
        elif intent == "DONATION_INQUIRY":
            extracted_entities = self.extract_entities(message)
            suggested_action = "CREATE_DONATION"
        elif intent == "FOOD_SAFETY":
            suggested_action = "INSPECT_FOOD_SAFETY"
        elif intent == "STATUS_TRACKING":
            suggested_action = "VIEW_TRACKING_STATUS"
        elif intent == "VOLUNTEER_INQUIRY":
            suggested_action = "OPEN_VOLUNTEER_TASKS"

        # 4. Retrieve or Compose Response
        kb_entry = self.KNOWLEDGE_BASE.get(intent, self.KNOWLEDGE_BASE["GREETING_HELP"])
        lang_response = kb_entry.get(lang, kb_entry["en"])

        response_text = lang_response["text"]
        followups = lang_response["followups"]
        english_translation = kb_entry["en"]["text"]

        return {
            "response": response_text,
            "detected_language": detected_lang,
            "response_language": lang,
            "language_name": self.LANGUAGES[lang],
            "intent": intent,
            "confidence": confidence,
            "english_translation": english_translation,
            "suggested_followups": followups,
            "extracted_entities": extracted_entities,
            "suggested_action": suggested_action,
            "model_architecture": "Calibrated SGD Classifier with Char-WB TF-IDF (2-5 grams)",
            "supported_languages": self.LANGUAGES
        }

multilingual_nlp_engine = MultilingualNLPEngine()
