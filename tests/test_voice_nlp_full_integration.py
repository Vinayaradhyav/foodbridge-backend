import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

from app.ai.chatbot.indic_nlp_engine import IndicNLPEngine, indic_nlp_engine
from app.ai.chatbot.emergency_nlp_parser import EmergencyNLPParser, emergency_nlp_parser
from app.models.emergency import EmergencyRequestCreate, EmergencyRequestResponse, EmergencyType, Urgency, EmergencyStatus
from app.services.emergency_service import EmergencyService


class TestVoiceNLPFullIntegration:
    """
    Exhaustive integration and benchmark suite for FoodBridge Voice Recording & NLP system:
    1. Single-sentence input
    2. 3-sentence pause-separated input (user benchmark)
    3. 5-sentence multi-entity complex input
    4. Kannada Dravidian input
    5. Hindi input
    6. Missing fields handling (no fabricated defaults)
    7. Urgency multi-factor scoring
    8. Database persistence and emergency request creation
    """

    def test_single_sentence_input(self):
        """Test 1: Single sentence extraction."""
        text = "Need 50 food packets urgently in Mysuru"
        res = indic_nlp_engine.extract_entities(text)

        assert res["food_quantity"] == 50
        assert res["delivery_location"] == "Mysuru"
        assert res["urgency"] in ["high", "critical"]
        assert res["original_language"] == "en"

    def test_three_sentence_benchmark_with_pauses(self):
        """
        Test 2: User's exact benchmark scenario:
        Sentence 1: 'There are 200 people in a shelter near Mysuru.'
        Sentence 2: 'We urgently need 500 cooked meals.'
        Sentence 3: 'The meals must be properly packaged, and we also need 200 water bottles tonight. This is a critical emergency.'
        """
        # Step A: Test accumulation via merge_voice_draft
        session_id = "test-session-123"
        draft = indic_nlp_engine.merge_voice_draft(session_id, None, "There are 200 people in a shelter near Mysuru.")
        assert draft["number_of_people"] == 200
        assert draft["delivery_location"] == "Mysuru"

        draft = indic_nlp_engine.merge_voice_draft(session_id, draft, "We urgently need 500 cooked meals.")
        assert draft["number_of_people"] == 200
        assert draft["food_quantity"] == 500
        assert draft["food_category"] == "Cooked Meals"

        draft = indic_nlp_engine.merge_voice_draft(
            session_id, draft,
            "The meals must be properly packaged, and we also need 200 water bottles tonight. This is a critical emergency."
        )

        # Step B: Assert all 12 parameters on the combined draft
        assert draft["delivery_location"] == "Mysuru"
        assert draft["number_of_people"] == 200
        assert draft["beneficiaries"] == 200
        assert draft["food_quantity"] == 500
        assert draft["quantity"] == 500
        assert draft["quantity_unit"] == "meals"
        assert draft["food_category"] == "Cooked Meals"
        assert draft["cooking_required"] is True
        assert draft["packaging_required"] is True
        assert draft["water_quantity"] == 200
        assert draft["delivery_time"] == "tonight"
        assert draft["urgency"] == "critical"
        assert draft["urgency_level"] == "CRITICAL"
        assert "200 Water Bottles" in draft["additional_requirements"]
        assert "Proper Sealed Packaging" in draft["additional_requirements"]

    def test_five_sentence_multi_entity_input(self):
        """Test 3: Complex multi-entity disaster relief input."""
        full_text = (
            "Flooding reported in shelter near Mysuru. "
            "Currently 350 people have arrived with zero provisions. "
            "Please deliver 700 freshly prepared meal boxes and 350 water bottles by today. "
            "Proper packaging is required. "
            "This is a critical emergency SOS situation."
        )
        res = indic_nlp_engine.extract_entities(full_text)

        assert res["delivery_location"] == "Mysuru"
        assert res["number_of_people"] == 350
        assert res["food_quantity"] == 700
        assert res["water_quantity"] == 350
        assert res["packaging_required"] is True
        assert res["urgency_level"] == "CRITICAL"
        assert res["emergency_type"] == "COMMUNITY_EMERGENCY"

    def test_kannada_dravidian_input(self):
        """
        Test 4: Pure Kannada emergency utterance with agglutinative inflections.
        'ತುರ್ತು: ಪ್ರವಾಹ ಸಂತ್ರಸ್ತರಿಗೆ ತಕ್ಷಣವೇ 300 ಊಟದ ಪೊಟ್ಟಣಗಳು ಮತ್ತು 100 ನೀರಿನ ಬಾಟಲಿಗಳು ಬೇಕು ಮೈಸೂರಿನಲ್ಲಿ'
        """
        kannada_text = "ತುರ್ತು: ಪ್ರವಾಹ ಸಂತ್ರಸ್ತರಿಗೆ ತಕ್ಷಣವೇ 300 ಊಟದ ಪೊಟ್ಟಣಗಳು ಮತ್ತು 100 ನೀರಿನ ಬಾಟಲಿಗಳು ಬೇಕು ಮೈಸೂರಿನಲ್ಲಿ"
        res = indic_nlp_engine.extract_entities(kannada_text)

        assert res["original_language"] == "kn"
        assert res["food_quantity"] == 300
        assert res["water_quantity"] == 100
        assert res["delivery_location"] == "Mysuru"
        assert res["urgency_level"] in ["CRITICAL", "HIGH"]
        assert "Mysuru" in res["english_translation"]
        assert "300" in res["english_translation"]
        assert "100" in res["english_translation"]

    def test_hindi_input(self):
        """
        Test 5: Hindi emergency utterance with Devanagari numerals / text.
        'आपातकालीन: मैसूर में 200 लोगों के लिए 500 भोजन और 200 पानी की बोतलें चाहिए'
        """
        hindi_text = "आपातकालीन: मैसूर में 200 लोगों के लिए 500 भोजन और 200 पानी की बोतलें चाहिए"
        res = indic_nlp_engine.extract_entities(hindi_text)

        assert res["original_language"] == "hi"
        assert res["number_of_people"] == 200
        assert res["food_quantity"] == 500
        assert res["water_quantity"] == 200
        assert res["delivery_location"] == "Mysuru"
        assert res["urgency_level"] in ["CRITICAL", "HIGH"]

    def test_missing_fields_handling_no_fabrication(self):
        """
        Test 6: Incomplete utterance must NOT invent values.
        Missing quantities must be None, and missing_fields must identify them.
        """
        incomplete_text = "We need help in Bengaluru"
        res = indic_nlp_engine.extract_entities(incomplete_text)

        assert res["food_quantity"] is None
        assert res["number_of_people"] is None
        assert res["delivery_location"] == "Bengaluru"
        assert "quantity" in res["missing_fields"]
        assert "number_of_people" in res["missing_fields"]
        assert res["is_complete"] is False

    def test_urgency_scoring_logic(self):
        """Test 7: Multi-factor contextual urgency scoring."""
        # Critical: SOS keywords + large scale (>200) + tonight deadline
        critical_text = "Critical emergency SOS: 250 people stranded without food tonight in Mysuru"
        res_critical = indic_nlp_engine.extract_entities(critical_text)
        assert res_critical["urgency_level"] == "CRITICAL"

        # Low urgency: inquiry with small quantity and no urgency keywords
        low_text = "We might need 10 apples for snacks next week"
        res_low = indic_nlp_engine.extract_entities(low_text)
        assert res_low["urgency_level"] in ["LOW", "MEDIUM"]

    def test_database_persistence_flow(self):
        """
        Test 8: Database persistence schema compatibility.
        Verifies that parsed NLP entities can be instantiated as EmergencyRequestCreate
        and saved via EmergencyService without Pydantic or MongoDB schema errors.
        """
        async def _run_async_test():
            parsed = indic_nlp_engine.extract_entities(
                "There are 200 people in a shelter near Mysuru. We urgently need 500 cooked meals tonight."
            )

            deadline = datetime.now(timezone.utc) + timedelta(hours=4)
            req_create = EmergencyRequestCreate(
                created_by="test_ngo_user_123",
                food_type=parsed["food_type"],
                food_category=parsed["food_category"],
                quantity=parsed["food_quantity"],
                quantity_unit=parsed["quantity_unit"],
                number_of_people=parsed["number_of_people"],
                location=parsed["delivery_location"],
                latitude=12.2958,
                longitude=76.6394,
                emergency_type=EmergencyType.COMMUNITY_EMERGENCY,
                urgency=Urgency.CRITICAL,
                deadline=deadline,
                description="Multi-sentence voice emergency request test",
                original_language=parsed["original_language"],
                original_transcript=parsed["original_transcript"],
                english_translation=parsed["english_translation"]
            )

            assert req_create.quantity == 500
            assert req_create.number_of_people == 200
            assert req_create.urgency == Urgency.CRITICAL

            # Mock MongoDB insert to verify service logic without requiring live network
            with patch("app.services.emergency_service.mongodb") as mock_mongo:
                mock_mongo.db.emergencies.insert_one = AsyncMock(return_value=True)
                mock_mongo.db.emergency_requests.insert_one = AsyncMock(return_value=True)
                mock_mongo.db.users.find.return_value.to_list = AsyncMock(return_value=[])

                response = await EmergencyService.create_emergency(req_create)

                assert isinstance(response, EmergencyRequestResponse)
                assert response.quantity == 500
                assert response.number_of_people == 200
                assert response.priority_score > 50.0
                assert "Critical Urgency" in response.priority_explanation
                assert mock_mongo.db.emergencies.insert_one.called

        asyncio.run(_run_async_test())
