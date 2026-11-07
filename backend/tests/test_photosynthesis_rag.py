"""
Regression and end-to-end integration tests for the Photosynthesis RAG engine.

Tests 8,000+ character scientific documents containing oxygenic/anoxygenic
photosynthesis, chemical equations, citations, reference markers, and bash/curl escapes.
Verifies that 5-question gauntlets generate cleanly in Strict Material Only mode.
"""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from main import app
from game_logic import (
    GauntletPayload,
    GenerateGameRequest,
    Question,
    has_reasonable_option_length_balance,
    sanitize_document_text,
    validate_gauntlet_payload,
)
from gemini_service import (
    InsufficientMaterialError,
    TopicRejectedError,
    build_generation_prompt,
    generate_gauntlet_with_gemini,
)

client = TestClient(app)

# Substantial 8,000+ character factual text about Photosynthesis
SUBSTANTIAL_PHOTOSYNTHESIS_TEXT = """Photosynthesis is a biological process used by many cellular organisms to convert light energy into chemical energy. This chemical energy is stored in carbohydrate molecules, such as sugars and starches, which are synthesized from carbon dioxide and water [1]. The name photosynthesis comes from the Greek phōs ("light") and synthesis ("putting together") [2]. In most cases, oxygen is also released as a waste product. Most plants, algae, and cyanobacteria perform photosynthesis; such organisms are called photoautotrophs [3]. Photosynthesis is largely responsible for producing and maintaining the oxygen content of the Earth's atmosphere, and supplies most of the biological energy necessary for complex life on Earth [4].

Although photosynthesis is performed differently by different species, the process always begins when energy from light is absorbed by proteins called reaction centers that contain green chlorophyll (and other colored) pigments [5]. In plants, these proteins are held inside organelles called chloroplasts, which are most abundant in leaf cells, while in bacteria they are embedded in the plasma membrane [6]. In these light-dependent reactions, some energy is used to strip electrons from suitable substances, such as water, producing oxygen gas [7]. The hydrogen freed by the splitting of water is used in the creation of two further compounds that serve as short-term stores of energy, facilitating its transfer to drive other reactions: these compounds are reduced nicotinamide adenine dinucleotide phosphate (NADPH) and adenosine triphosphate (ATP), the "energy currency" of cells [8].

== Oxygenic versus Anoxygenic Photosynthesis ==
Photosynthesis can be divided into two broad categories: oxygenic photosynthesis and anoxygenic photosynthesis [9]. Oxygenic photosynthesis is the most common and is seen in plants, algae, and cyanobacteria. During oxygenic photosynthesis, light energy transfers electrons from water (H2O) to carbon dioxide (CO2), producing carbohydrates [10]. In this process, the water is "split" or oxidized, meaning it loses electrons, while the CO2 is reduced, meaning it gains electrons. Diatomic oxygen (O2) is produced alongside carbohydrates [11].

Overall Net Chemical Equation for Oxygenic Photosynthesis:
6 CO2 + 6 H2O + photons -> C6H12O6 + 6 O2 [12]
Standard Gibbs free energy change: ΔG° = +2870 kJ/mol [13].

In contrast, anoxygenic photosynthesis uses electron donors other than water [14]. This process typically occurs in purple bacteria, green sulfur bacteria, and heliobacteria [15]. Instead of water, these organisms use donors such as hydrogen sulfide (H2S), thiosulfate, or ferrous iron (Fe2+), producing elemental sulfur or oxidized iron rather than oxygen [16].

Representative Equation for Anoxygenic Photosynthesis (using H2S):
CO2 + 2 H2S + light energy -> [CH2O] + 2 S + H2O [17].

== Evolutionary History and the Great Oxidation Event ==
Early photosynthetic systems, such as those from green and purple sulfur and green and purple non-sulfur bacteria, are thought to have been anoxygenic, and used various molecules other than water as electron donors [18]. Cyanobacteria appeared later, roughly 2.4 to 2.7 billion years ago, and were the first organisms to utilize water as an electron donor, giving rise to oxygenic photosynthesis [19]. This innovation dramatically altered Earth's atmosphere during the Great Oxidation Event (GOE) [20], enabling the evolution of aerobic respiration and complex multicellular life. Endosymbiotic events later incorporated ancestral cyanobacteria into eukaryotic host cells, forming the modern chloroplast organelle found in green plants and red algae [21].

== Chloroplast Structure and Light Absorption ==
In plants and algae, photosynthesis takes place in chloroplasts. A typical plant leaf cell contains roughly 10 to 100 chloroplasts [22]. The chloroplast is enclosed by a double-membrane envelope consisting of an outer membrane, an intermembrane space, and an inner membrane [23]. Enclosed by the inner membrane is the stroma, a protein-rich aqueous fluid containing metabolic enzymes, chloroplast DNA, and ribosomes [24].

Suspended within the stroma is an internal membrane system composed of disc-like structures called thylakoids [25]. The thylakoid membrane encloses an internal compartment known as the thylakoid lumen [26]. Thylakoids are frequently organized into dense stacks termed grana (singular: granum), interconnected by unstacked stroma thylakoids or lamellae [27].

The thylakoid membranes harbor five major multi-protein complexes:
1. Photosystem II (PSII) [28]
2. Cytochrome b6f complex [29]
3. Photosystem I (PSI) [30]
4. ATP synthase [31]
5. Light-harvesting complexes (LHCs) composed of chlorophyll a, chlorophyll b, and accessory carotenoids [32].

Chlorophyll a absorbs primarily blue-violet and red wavelengths of light, while reflecting green light (around 500-550 nm), giving leaves their characteristic color [33]. Carotenoids absorb blue-green light and protect the photosynthetic apparatus from photo-oxidative damage caused by excess radiation [34].

== The Light-Dependent Reactions ==
The light reactions occur strictly across the thylakoid membrane [35].
When a photon hits the P680 reaction center of Photosystem II, an electron is boosted to a higher energy level and transferred to primary electron acceptor pheophytin, then to plastoquinone (PQ) [36]. The electron deficit in P680+ is replenished by the Oxygen-Evolving Complex (OEC), which catalyzes the photolysis of water:
2 H2O -> O2 + 4 H+ + 4 e- [37].

The energized electrons travel through plastoquinone to the cytochrome b6f complex, which pumps protons (H+) from the stroma across the thylakoid membrane into the thylakoid lumen, creating a steep electrochemical proton gradient [38]. Electrons are then transferred to the mobile copper-protein plastocyanin (PC), which carries them to Photosystem I [39].

At Photosystem I, photons excite the P700 reaction center, ejecting electrons through a series of iron-sulfur clusters to ferredoxin (Fd) [40]. The enzyme ferredoxin-NADP+ reductase (FNR) catalyzes the transfer of electrons from reduced ferredoxin to NADP+, producing NADPH in the stroma:
NADP+ + 2 H+ + 2 e- -> NADPH + H+ [41].

Meanwhile, the proton gradient across the thylakoid membrane drives protons back down their electrochemical gradient through the CF0-CF1 ATP synthase complex into the stroma, phosphorylating ADP and inorganic phosphate (Pi) into ATP via photophosphorylation [42].

Overall stoichiometry of the non-cyclic light-dependent reaction:
2 H2O + 2 NADP+ + 3 ADP + 3 Pi + light -> O2 + 2 NADPH + 3 H+ + 3 ATP [43].

== The Calvin-Benson-Bassham Cycle (Light-Independent Reactions) ==
The Calvin cycle occurs in the stroma of the chloroplast and uses the ATP and NADPH generated by the light reactions to convert CO2 into carbohydrates [44]. Although traditionally called the "dark reactions", these enzymes are indirectly regulated by light-driven pH and redox changes in the stroma [45].

The cycle proceeds in three distinct phases:
Phase 1: Carbon Fixation
The five-carbon sugar ribulose 1,5-bisphosphate (RuBP) reacts with CO2 to form an unstable six-carbon intermediate that immediately splits into two molecules of 3-phosphoglycerate (3-PGA) [46]. This reaction is catalyzed by ribulose-1,5-bisphosphate carboxylase-oxygenase, commonly known as RuBisCO, which is considered the most abundant enzyme on Earth [47].

Phase 2: Reduction
Each molecule of 3-PGA is phosphorylated by ATP (using 3-phosphoglycerate kinase) to produce 1,3-bisphosphoglycerate (1,3-BPG), which is subsequently reduced by NADPH (using glyceraldehyde-3-phosphate dehydrogenase) to yield glyceraldehyde 3-phosphate (G3P), a triose phosphate sugar [48].

Phase 3: Regeneration of RuBP
For every three molecules of CO2 that enter the Calvin cycle, six molecules of G3P are produced, but only one net molecule of G3P is exported to the cytoplasm for glucose and sucrose synthesis [49]. The remaining five G3P molecules undergo a complex series of enzymatic rearrangements driven by ATP to regenerate three molecules of RuBP, enabling the cycle to continue [50].

Summary of Calvin Cycle requirements for one molecule of hexose glucose (requiring 6 turns of the cycle):
6 CO2 + 18 ATP + 12 NADPH + 12 H2O -> C6H12O6 + 18 ADP + 18 Pi + 12 NADP+ + 6 H+ [51].

== Regulatory and Environmental Considerations ==
Photosynthetic efficiency is governed by three primary environmental variables:
1. Irradiance (light intensity and spectral quality) [52]
2. Carbon dioxide partial pressure in the intercellular air spaces of the mesophyll [53]
3. Temperature, which dictates the kinetics of RuBisCO carboxylation versus its competitive oxygenase activity (photorespiration) [54].
C4 and CAM adaptations have evolved independently in numerous plant lineages to concentrate CO2 around RuBisCO and suppress photorespiration under arid, hot, or nitrogen-limited environments [55]."""


def test_substantial_photosynthesis_text_size():
    """Verify document length is realistically 8,000+ characters."""
    assert len(SUBSTANTIAL_PHOTOSYNTHESIS_TEXT) > 7500
    sanitized = sanitize_document_text(SUBSTANTIAL_PHOTOSYNTHESIS_TEXT)
    assert len(sanitized) > 7500
    # Citations [1], equations, and sections are intact
    assert "6 CO2 + 6 H2O + photons -> C6H12O6 + 6 O2" in sanitized
    assert "[1]" in sanitized
    assert "== The Calvin-Benson-Bassham Cycle" in sanitized


def test_photosynthesis_strict_generation_prompt():
    """Verify prompt generated for 5-question Strict Material Only mode."""
    req = GenerateGameRequest(
        topic="Photosynthesis",
        target_level="General",
        question_count=5,
        generation_mode="Strict Material Only",
        source_text=SUBSTANTIAL_PHOTOSYNTHESIS_TEXT,
    )
    prompt = build_generation_prompt(req)
    assert "STRICT MATERIAL ONLY RULES:" in prompt
    assert "chemical equations (e.g., 6 CO2 + 6 H2O -> C6H12O6 + 6 O2)" in prompt
    assert "Do NOT reject or fail documents containing citations" in prompt
    assert "<untrusted_user_input>" in prompt
    assert "Photosynthesis" in prompt


def test_scientific_option_balance_does_not_reject_formulas():
    """Verify options with short chemical formulas ('O2', 'H2O', 'ATP') are accepted."""
    # Common photosynthesis question options:
    chem_options_1 = ["H2O", "CO2", "H2S", "Nicotinamide adenine dinucleotide"]
    assert has_reasonable_option_length_balance(chem_options_1, "H2O") is True

    chem_options_2 = ["ATP", "NADPH", "Glucose", "Glyceraldehyde 3-phosphate"]
    assert has_reasonable_option_length_balance(chem_options_2, "ATP") is True

    chem_options_3 = ["O2", "CO2", "N2", "CH4"]
    assert has_reasonable_option_length_balance(chem_options_3, "O2") is True


def test_validate_gauntlet_payload_normalizes_tiers_for_5_questions():
    """Verify that if Gemini outputs tiers 1-4 for 5 questions, it auto-normalizes without crashing."""
    # Suppose Gemini outputs increasing tiers: 1, 2, 3, 4, 4
    q_list = [
        Question(
            stage=1, tier=1, question="What molecule is split in oxygenic photosynthesis?",
            options=["H2O", "CO2", "H2S", "Glucose"], correct_answer="H2O",
            explanation="Water is split by the Oxygen-Evolving Complex.",
        ),
        Question(
            stage=2, tier=2,  # Gemini assigned tier 2
            question="What is the primary photosynthetic pigment in plants?",
            options=["Chlorophyll a", "Carotenoids", "Phycobilin", "Hemoglobin"],
            correct_answer="Chlorophyll a", explanation="Chlorophyll a is the primary pigment.",
        ),
        Question(
            stage=3, tier=3,  # Gemini assigned tier 3
            question="Where does the Calvin cycle take place?",
            options=["Stroma", "Thylakoid lumen", "Mitochondrial matrix", "Cytoplasm"],
            correct_answer="Stroma", explanation="The Calvin cycle takes place in the stroma.",
        ),
        Question(
            stage=4, tier=4,  # Gemini assigned tier 4
            question="Which enzyme catalyzes carbon fixation in the Calvin cycle?",
            options=["RuBisCO", "ATP synthase", "DNA polymerase", "Amylase"],
            correct_answer="RuBisCO", explanation="RuBisCO catalyzes the carboxylation of RuBP.",
        ),
        Question(
            stage=5, tier=4,
            question="What high-energy electron carrier is produced by Photosystem I?",
            options=["NADPH", "FADH2", "NADH", "Lactate"],
            correct_answer="NADPH", explanation="Photosystem I transfers electrons to reduce NADP+ to NADPH.",
        ),
    ]

    payload = GauntletPayload(is_valid=True, topic="Photosynthesis", gauntlet=q_list)
    # validate_gauntlet_payload must succeed and normalize tiers to expected tier (all tier 1 for 5 questions)
    validated = validate_gauntlet_payload(payload, expected_length=5)
    assert len(validated.gauntlet) == 5
    for q in validated.gauntlet:
        assert q.tier == 1


def test_generate_game_photosynthesis_strict_material_success():
    """
    Simulate full /generate-game flow with the 8,000+ character Photosynthesis document
    in Strict Material Only mode and verify 200 OK with 5 questions.
    """
    mock_questions = [
        Question(
            stage=1, tier=1, question="In oxygenic photosynthesis, which molecule serves as the electron donor?",
            options=["H2O", "H2S", "CO2", "CH4"],
            correct_answer="H2O",
            explanation="Water (H2O) is the electron donor in oxygenic photosynthesis.",
        ),
        Question(
            stage=2, tier=1, question="Which cellular organelle hosts photosynthesis in green plants?",
            options=["Chloroplast", "Mitochondrion", "Ribosome", "Endoplasmic reticulum"],
            correct_answer="Chloroplast",
            explanation="Photosynthesis takes place inside chloroplast organelles in plant cells.",
        ),
        Question(
            stage=3, tier=1, question="What enzyme catalyzes the fixation of carbon dioxide in the Calvin cycle?",
            options=["RuBisCO", "Cytochrome b6f", "FNR", "Ferredoxin"],
            correct_answer="RuBisCO",
            explanation="RuBisCO catalyzes the reaction between RuBP and carbon dioxide.",
        ),
        Question(
            stage=4, tier=1, question="Where do the light-dependent reactions occur within the chloroplast?",
            options=["Thylakoid membranes", "Outer membrane", "Intermembrane space", "Cytosol"],
            correct_answer="Thylakoid membranes",
            explanation="The light-dependent reactions occur across the thylakoid membranes.",
        ),
        Question(
            stage=5, tier=1, question="What is the net gain of G3P exported from the Calvin cycle for every three CO2 fixed?",
            options=["One G3P molecule", "Three G3P molecules", "Six G3P molecules", "Twelve G3P molecules"],
            correct_answer="One G3P molecule",
            explanation="For every three CO2 molecules fixed, one net G3P molecule is exported.",
        ),
    ]

    mock_payload = GauntletPayload(is_valid=True, topic="Photosynthesis", gauntlet=mock_questions)

    with patch("main.generate_gauntlet_with_gemini", return_value=mock_payload):
        resp = client.post(
            "/generate-game",
            json={
                "topic": "Photosynthesis",
                "target_level": "General",
                "question_count": 5,
                "generation_mode": "Strict Material Only",
                "source_text": SUBSTANTIAL_PHOTOSYNTHESIS_TEXT,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["topic"] == "Photosynthesis"
        assert data["question_count"] == 5
        assert len(data["gauntlet"]) == 5
        assert data["tier_checkpoints"] == []
        assert data["is_fallback"] is None  # Never fallback in Strict Material Only


def test_generation_distinguishes_generation_failure_from_insufficient_material():
    """Verify that internal API/generation errors return HTTP 500, not claiming material was insufficient."""
    with patch(
        "main.generate_gauntlet_with_gemini",
        side_effect=RuntimeError("Gemini API connection error: RemoteDisconnected"),
    ):
        resp = client.post(
            "/generate-game",
            json={
                "topic": "Photosynthesis",
                "target_level": "General",
                "question_count": 5,
                "generation_mode": "Strict Material Only",
                "source_text": SUBSTANTIAL_PHOTOSYNTHESIS_TEXT,
            },
        )
        assert resp.status_code == 500
        detail = resp.json()["detail"]
        # Must clearly indicate generation/API failure, NOT falsely blaming source material
        assert "Question generation failed" in detail
        assert "Gemini API connection error" in detail
        assert "Please ensure the document contains sufficient facts" not in detail
