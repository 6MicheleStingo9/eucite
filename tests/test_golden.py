"""Golden nodes of the real corpus, checked by hand (plan S3).

Each expectation was read against the XHTML manifestation of the same work and
language, an independent rendering by the Publications Office, on 8 October
2026. The known differences between the two renderings are the ones ADR-0006
lists: the XHTML loses the superscript of 10^25, shows a deleted provision as
its amendment marker followed by a rule, and lays tables out differently.

The list covers the cases the plan names (Article 3, point (14a); the second
subparagraph of Article 6(3); Article 43(1); Article 14(4)(b); the indents of
Annex II; Annex VII, point 3.1; a table of Annex XIV; a recital of the Omnibus)
and the cases found while writing the parser: deletions, a marker spanning two
elements, implicit amendments, an inserted article, a replaced heading,
formatted numbers, quoted provisions.
"""

from __future__ import annotations

import pytest

from tests.test_corpus import document

pytestmark = pytest.mark.data

GOLDEN: list[tuple[str, str, str, dict[str, object]]] = [
    (
        "02024R1689-20260727",
        "eng",
        "art_3.subpara_1.point_14a",
        {
            "label": "(14a)",
            "heading": None,
            "parent": "art_3.subpara_1",
            "amendments": (("inserted", "whole", "AR:1;PT:14;PT:b", False),),
            "notes": 0,
            "text": (
                "\u2018micro, small and medium-sized enterprise\u2019 "
                "or \u2018SME\u2019 means a micro, "
                "small or medium-sized enterprise as defined in Article 2 of the Annex "
                "to Recommendation 2003/361/EC;"
            ),
        },
    ),
    (
        "02024R1689-20260727",
        "ita",
        "art_3.subpara_1.point_14a",
        {
            "label": "14 bis)",
            "heading": None,
            "parent": "art_3.subpara_1",
            "amendments": (("inserted", "whole", "AR:1;PT:14;PT:b", False),),
            "notes": 0,
            "text": (
                "\xabmicroimprese, piccole e medie imprese\xbb "
                "o \xabPMI\xbb: microimprese, piccole "
                "o medie imprese quali definite all'articolo 2 dell'allegato della "
                "raccomandazione 2003/361/CE;"
            ),
        },
    ),
    (
        "02024R1689-20260727",
        "eng",
        "art_6.para_3.subpara_2",
        {
            "label": None,
            "heading": None,
            "parent": "art_6.para_3",
            "amendments": (),
            "notes": 0,
            "text": (
                "The first subparagraph shall apply where any of the following "
                "conditions is fulfilled:\n(a) the AI system is intended to perform a "
                "narrow procedural task;\n(b) the AI system is intended to improve the "
                "result of a previously completed human activity;\n(c) the AI system is "
                "intended to detect decision-making patterns or deviations from prior "
                "decision-making patterns and is not meant to replace or influence the "
                "previously completed human assessment, without proper human review; "
                "or\n(d) the AI system is intended to perform a preparatory task to an "
                "assessment relevant for the purposes of the use cases listed in Annex "
                "III."
            ),
        },
    ),
    (
        "02024R1689-20260727",
        "eng",
        "art_43.para_1.subpara_1.point_a",
        {
            "label": "(a)",
            "heading": None,
            "parent": "art_43.para_1.subpara_1",
            "amendments": (),
            "notes": 0,
            "text": "the internal control referred to in Annex VI; or",
        },
    ),
    (
        "02024R1689-20260727",
        "eng",
        "art_43.para_1.subpara_2.point_a",
        {
            "label": "(a)",
            "heading": None,
            "parent": "art_43.para_1.subpara_2",
            "amendments": (),
            "notes": 0,
            "text": (
                "harmonised standards referred to in Article 40 do not exist, and common "
                "specifications referred to in Article 41 are not available;"
            ),
        },
    ),
    (
        "02024R1689-20260727",
        "eng",
        "art_14.para_4.subpara_1.point_b",
        {
            "label": "(b)",
            "heading": None,
            "parent": "art_14.para_4.subpara_1",
            "amendments": (),
            "notes": 0,
            "text": (
                "to remain aware of the possible tendency of automatically relying or "
                "over-relying on the output produced by a high-risk AI system "
                "(automation bias), in particular for high-risk AI systems used to "
                "provide information or recommendations for decisions to be taken by "
                "natural persons;"
            ),
        },
    ),
    (
        "02024R1689-20260727",
        "eng",
        "anx_II.indent_3",
        {
            "label": None,
            "heading": None,
            "parent": "anx_II",
            "amendments": (),
            "notes": 0,
            "text": "sexual exploitation of children, and child pornography,",
        },
    ),
    (
        "02024R1689-20260727",
        "eng",
        "anx_VII.sct_3.point_3-1",
        {
            "label": "3.1.",
            "heading": None,
            "parent": "anx_VII.sct_3",
            "amendments": (),
            "notes": 0,
            "text": (
                "The application of the provider shall include:\n(a) the name and address "
                "of the provider and, if the application is lodged by an authorised "
                "representative, also their name and address;\n(b) the list of AI systems "
                "covered under the same quality management system;\n(c) the technical "
                "documentation for each AI system covered under the same quality "
                "management system;\n(d) the documentation concerning the quality "
                "management system which shall cover all the aspects listed under "
                "Article 17;\n(e) a description of the procedures in place to ensure that "
                "the quality management system remains adequate and effective;\n(f) a "
                "written declaration that the same application has not been lodged with "
                "any other notified body."
            ),
        },
    ),
    (
        "02024R1689-20260727",
        "eng",
        "anx_XIV.sct_2.sct_b.table_1",
        {
            "label": None,
            "heading": None,
            "parent": "anx_XIV.sct_2.sct_b",
            "amendments": (("inserted", "whole", "AR:1;PT:43", False),),
            "notes": 0,
            "text": (
                "AIA Code |\nAIB 0201 | Remote biometric identification systems\nAIB 0202 "
                "| Biometric categorisation AI systems\nAIB 0203 | Emotion recognition AI "
                "systems"
            ),
        },
    ),
    (
        "32026R1744",
        "eng",
        "rct_1",
        {
            "label": "(1)",
            "heading": None,
            "parent": "32026R1744",
            "amendments": (),
            "notes": 1,
            "text": (
                "Regulation (EU) 2024/1689 of the European Parliament and of the Council "
                "lays down harmonised rules on artificial intelligence (AI) and aims to "
                "improve the functioning of the internal market, to promote the uptake "
                "of human-centric and trustworthy AI, while ensuring a high level of "
                "protection of health, safety and fundamental rights and supporting "
                "innovation. Regulation (EU) 2024/1689 entered into force on 1 August "
                "2024. The entry into application of its provisions is staggered, with "
                "all rules entering into application by 2 August 2027."
            ),
        },
    ),
    (
        "02024R1689-20260727",
        "eng",
        "art_10.para_5",
        {
            "label": "5.",
            "heading": None,
            "parent": "art_10",
            "amendments": (("deleted", "whole", "AR:1;PT:9;PT:b", False),),
            "notes": 0,
            "text": None,
        },
    ),
    (
        "02024R1689-20260727",
        "eng",
        "art_58.para_1",
        {
            "label": "1.",
            "heading": None,
            "parent": "art_58",
            "amendments": (("replaced", "part", "AR:1;PT:23;PT:a", False),),
            "notes": 0,
            "text": (
                "In order to avoid fragmentation across the Union, the Commission shall "
                "adopt implementing acts specifying the detailed arrangements for the "
                "establishment, development, implementation, operation, governance, and "
                "supervision of the AI regulatory sandboxes. Those implementing acts "
                "shall include common principles on the following issues:\n(a) "
                "eligibility and selection criteria for participation in the AI "
                "regulatory sandbox;\n(b) procedures for the application, participation, "
                "monitoring, exiting from and termination of the AI regulatory sandbox, "
                "including the sandbox plan and the exit report;\n(c) the terms and "
                "conditions applicable to the participants;\n(d) the detailed rules "
                "applicable to the governance of AI regulatory sandboxes covered "
                "pursuant to Article 57, including as regards the involvement of and "
                "supervision by the competent data protection authorities, where "
                "relevant, and the coordination and cooperation at national and Union "
                "level.\nThose implementing acts shall be adopted in accordance with the "
                "examination procedure referred to in Article 98(2)."
            ),
        },
    ),
    (
        "02024R1689-20260727",
        "eng",
        "art_58.para_1.subpara_1.point_c",
        {
            "label": "(c)",
            "heading": None,
            "parent": "art_58.para_1.subpara_1",
            "amendments": (("replaced", "part", "AR:1;PT:23;PT:b", True),),
            "notes": 0,
            "text": "the terms and conditions applicable to the participants;",
        },
    ),
    (
        "02024R1689-20260727",
        "eng",
        "art_58.para_1.subpara_1.point_d",
        {
            "label": "(d)",
            "heading": None,
            "parent": "art_58.para_1.subpara_1",
            "amendments": (("inserted", "whole", "AR:1;PT:23;PT:b", False),),
            "notes": 0,
            "text": (
                "the detailed rules applicable to the governance of AI regulatory "
                "sandboxes covered pursuant to Article 57, including as regards the "
                "involvement of and supervision by the competent data protection "
                "authorities, where relevant, and the coordination and cooperation at "
                "national and Union level."
            ),
        },
    ),
    (
        "02024R1689-20260727",
        "eng",
        "art_25.para_4",
        {
            "label": "4.",
            "heading": None,
            "parent": "art_25",
            "amendments": (("replaced", "part", "AR:1;PT:12;PT:b", False),),
            "notes": 0,
            "first_line": (
                "The provider of a high-risk AI system and the third party that supplies "
                "an AI system, AI model, tools, services, components, or processes that "
                "are used or integrated in a high-risk AI system shall, by written "
                "agreement, specify the necessary information, capabilities, technical "
                "access and other assistance based on the generally acknowledged state "
                "of the art, in order to enable the provider of the high-risk AI system "
                "to fully comply with the obligations set out in this Regulation. This "
                "paragraph shall not apply to third parties making accessible to the "
                "public tools, services, processes, or components, other than "
                "general-purpose AI models, under a free and open-source licence."
            ),
            "last_line": (
                "The AI Office may develop and recommend voluntary model terms for "
                "contracts between providers of high-risk AI systems and third parties "
                "that supply tools, services, components or processes that are used for "
                "or integrated into high-risk AI systems. When developing those "
                "voluntary model terms, the AI Office shall take into account possible "
                "contractual requirements applicable in specific sectors or business "
                "cases. The voluntary model terms shall be published and be available "
                "free of charge in an easily usable electronic format."
            ),
            "lines": 2,
        },
    ),
    (
        "02024R1689-20260727",
        "eng",
        "art_25.para_4.subpara_1",
        {
            "label": None,
            "heading": None,
            "parent": "art_25.para_4",
            "amendments": (("replaced", "whole", "AR:1;PT:12;PT:b", False),),
            "notes": 0,
            "text": (
                "The provider of a high-risk AI system and the third party that supplies "
                "an AI system, AI model, tools, services, components, or processes that "
                "are used or integrated in a high-risk AI system shall, by written "
                "agreement, specify the necessary information, capabilities, technical "
                "access and other assistance based on the generally acknowledged state "
                "of the art, in order to enable the provider of the high-risk AI system "
                "to fully comply with the obligations set out in this Regulation. This "
                "paragraph shall not apply to third parties making accessible to the "
                "public tools, services, processes, or components, other than "
                "general-purpose AI models, under a free and open-source licence."
            ),
        },
    ),
    (
        "02024R1689-20260727",
        "eng",
        "art_4a",
        {
            "label": "Article 4a",
            "heading": (
                "Processing of special categories of personal data for bias detection "
                "and correction"
            ),
            "parent": "cpt_I",
            "amendments": (("inserted", "whole", "AR:1;PT:6", False),),
            "notes": 0,
            "first_line": (
                "1. To the extent strictly necessary to ensure bias detection and "
                "correction in relation to high-risk AI systems in accordance with "
                "Article 10(2), points (f) and (g), of this Regulation, providers of "
                "such systems may exceptionally process special categories of personal "
                "data, subject to appropriate safeguards for the fundamental rights and "
                "freedoms of natural persons. In addition to the provisions set out in "
                "Regulations (EU) 2016/679 and (EU) 2018/1725 and Directive (EU) "
                "2016/680, as applicable, all the following conditions shall be met in "
                "order for such processing to occur:"
            ),
            "last_line": (
                "This paragraph does not create any obligation to conduct such bias "
                "detection and correction."
            ),
            "lines": 11,
        },
    ),
    (
        "02024R1689-20260727",
        "ita",
        "art_4a",
        {
            "label": "Articolo 4 bis",
            "heading": (
                "Trattamento di categorie particolari di dati personali ai fini del "
                "rilevamento e della correzione delle distorsioni"
            ),
            "parent": "cpt_I",
            "amendments": (("inserted", "whole", "AR:1;PT:6", False),),
            "notes": 0,
            "first_line": (
                "1. Nella misura strettamente necessaria a garantire il rilevamento e la "
                "correzione delle distorsioni in relazione ai sistemi di IA ad alto "
                "rischio in conformit\xe0 dell'articolo 10, paragrafo 2, lettere f) e g), "
                "del presente regolamento, i fornitori di tali sistemi possono "
                "eccezionalmente trattare categorie particolari di dati personali, fatte "
                "salve le tutele adeguate per i diritti e le libert\xe0 fondamentali delle "
                "persone fisiche. Oltre alle disposizioni di cui ai regolamenti (UE) "
                "2016/679 e (UE) 2018/1725 e alla direttiva (UE) 2016/680, a seconda dei "
                "casi, sono soddisfatte, affinch\xe9 tale trattamento avvenga, tutte le "
                "condizioni seguenti:"
            ),
            "last_line": (
                "Il presente paragrafo non crea alcun obbligo di rilevare e correggere "
                "tali distorsioni."
            ),
            "lines": 11,
        },
    ),
    (
        "02024R1689-20260727",
        "eng",
        "art_75",
        {
            "label": "Article 75",
            "heading": "Market surveillance and control of AI systems and mutual assistance",
            "parent": "cpt_IX.sct_3",
            "amendments": (("replaced", "part", "AR:1;PT:31;PT:a", False),),
            "notes": 0,
            "first_line": (
                "1. The AI Office shall be exclusively competent for the supervision and "
                "enforcement of the obligations under this Regulation in relation to the "
                "following AI systems:"
            ),
            "last_line": (
                "3. Where a market surveillance authority is unable to conclude its "
                "investigation of the high-risk AI system because of its inability to "
                "access certain information related to the general-purpose AI model "
                "despite having made all appropriate efforts to obtain that information, "
                "it may submit a reasoned request to the AI Office, by which access to "
                "that information shall be enforced. In that case, the AI Office shall "
                "supply to the applicant authority without delay, and in any event "
                "within 30 days, any information that the AI Office considers to be "
                "relevant in order to establish whether a high-risk AI system is "
                "non-compliant. Market surveillance authorities shall safeguard the "
                "confidentiality of the information that they obtain in accordance with "
                "Article 78 of this Regulation. The procedure provided for in Chapter VI "
                "of Regulation (EU) 2019/1020 shall apply mutatis mutandis."
            ),
            "lines": 22,
        },
    ),
    (
        "02024R1689-20260727",
        "eng",
        "art_51.para_2",
        {
            "label": "2.",
            "heading": None,
            "parent": "art_51",
            "amendments": (),
            "notes": 0,
            "text": (
                "A general-purpose AI model shall be presumed to have high impact "
                "capabilities pursuant to paragraph 1, point (a), when the cumulative "
                "amount of computation used for its training measured in floating point "
                "operations is greater than 10^25."
            ),
        },
    ),
    (
        "02024R1689-20260727",
        "eng",
        "anx_I.sct_a.point_1",
        {
            "label": "1.",
            "heading": None,
            "parent": "anx_I.sct_a",
            "amendments": (("deleted", "whole", "AR:1;PT:41;PT:a", False),),
            "notes": 0,
            "text": None,
        },
    ),
    (
        "02024R1689-20260727",
        "eng",
        "anx_I.sct_b.point_21",
        {
            "label": "21.",
            "heading": None,
            "parent": "anx_I.sct_b",
            "amendments": (("inserted", "whole", "AR:1;PT:41;PT:b", False),),
            "notes": 0,
            "text": (
                "Regulation (EU) 2023/1230 of the European Parliament and of the Council "
                "of 14 June 2023 on machinery and repealing Directive 2006/42/EC of the "
                "European Parliament and of the Council and Council Directive 73/361/EEC "
                "(OJ L 165, 29.6.2023, p. 1, ELI: "
                "http://data.europa.eu/eli/reg/2023/1230/oj)."
            ),
        },
    ),
    (
        "02024R1689-20260727",
        "eng",
        "anx_VIII.sct_b.point_7",
        {
            "label": "7.",
            "heading": None,
            "parent": "anx_VIII.sct_b",
            "amendments": (("deleted", "whole", "AR:1;PT:42", False),),
            "notes": 0,
            "text": None,
        },
    ),
    (
        "02024R1689-20260727",
        "eng",
        "anx_VIII.sct_b.point_8",
        {
            "label": "8.",
            "heading": None,
            "parent": "anx_VIII.sct_b",
            "amendments": (("replaced", "part", "AR:1;PT:42", True),),
            "notes": 0,
            "text": (
                "The status of the AI system (on the market, or in service; no longer "
                "placed on the market/in service, recalled)."
            ),
        },
    ),
    (
        "02024R1689-20260727",
        "eng",
        "cpt_III.sct_2",
        {
            "label": "SECTION 2",
            "heading": "Requirements for high-risk AI systems",
            "parent": "cpt_III",
            "amendments": (),
            "notes": 0,
            "text": None,
        },
    ),
    (
        "32024R1689",
        "ita",
        "rct_1",
        {
            "label": "(1)",
            "heading": None,
            "parent": "32024R1689",
            "amendments": (),
            "notes": 0,
            "text": (
                "Lo scopo del presente regolamento \xe8 migliorare il funzionamento del "
                "mercato interno istituendo un quadro giuridico uniforme in particolare "
                "per quanto riguarda lo sviluppo, l'immissione sul mercato, la messa in "
                "servizio e l'uso di sistemi di intelligenza artificiale (sistemi di IA) "
                "nell'Unione, in conformit\xe0 dei valori dell'Unione, promuovere la "
                "diffusione di un'intelligenza artificiale (IA) antropocentrica e "
                "affidabile, garantendo nel contempo un livello elevato di protezione "
                "della salute, della sicurezza e dei diritti fondamentali sanciti dalla "
                "Carta dei diritti fondamentali dell'Unione europea (\xabCarta\xbb), compresi "
                "la democrazia, lo Stato di diritto e la protezione dell'ambiente, "
                "proteggere contro gli effetti nocivi dei sistemi di IA nell'Unione, "
                "nonch\xe9 promuovere l'innovazione. Il presente regolamento garantisce la "
                "libera circolazione transfrontaliera di beni e servizi basati sull'IA, "
                "impedendo cos\xec agli Stati membri di imporre restrizioni allo sviluppo, "
                "alla commercializzazione e all'uso di sistemi di IA, salvo espressa "
                "autorizzazione del presente regolamento."
            ),
        },
    ),
    (
        "32024R1689",
        "eng",
        "cit_1",
        {
            "label": None,
            "heading": None,
            "parent": "32024R1689",
            "amendments": (),
            "notes": 0,
            "text": (
                "Having regard to the Treaty on the Functioning of the European Union, "
                "and in particular Articles 16 and 114 thereof,"
            ),
        },
    ),
    (
        "02024R1689-20260727",
        "eng",
        "anx_X.sct_1.point_a",
        {
            "label": "(a)",
            "heading": None,
            "parent": "anx_X.sct_1",
            "amendments": (),
            "notes": 0,
            "text": (
                "Regulation (EU) 2018/1860 of the European Parliament and of the Council "
                "of 28 November 2018 on the use of the Schengen Information System for "
                "the return of illegally staying third-country nationals (OJ L 312, "
                "7.12.2018, p. 1)."
            ),
        },
    ),
    (
        "02024R1689-20260727",
        "eng",
        "art_99.para_3",
        {
            "label": "3.",
            "heading": None,
            "parent": "art_99",
            "amendments": (),
            "notes": 0,
            "text": (
                "Non-compliance with the prohibition of the AI practices referred to in "
                "Article 5 shall be subject to administrative fines of up to EUR 35 000 "
                "000 or, if the offender is an undertaking, up to 7 % of its total "
                "worldwide annual turnover for the preceding financial year, whichever "
                "is higher."
            ),
        },
    ),
    (
        "02024R1689-20260727",
        "ita",
        "art_99.para_3",
        {
            "label": "3.",
            "heading": None,
            "parent": "art_99",
            "amendments": (),
            "notes": 0,
            "text": (
                "La non conformit\xe0 al divieto delle pratiche di IA di cui all'articolo 5 "
                "\xe8 soggetta a sanzioni amministrative pecuniarie fino a 35 000 000 EUR "
                "o, se l'autore del reato \xe8 un'impresa, fino al 7 % del fatturato "
                "mondiale totale annuo dell'esercizio precedente, se superiore."
            ),
        },
    ),
    (
        "02024R1689-20260727",
        "eng",
        "anx_III.point_1.point_a",
        {
            "label": "(a)",
            "heading": None,
            "parent": "anx_III.point_1",
            "amendments": (),
            "notes": 0,
            "text": (
                "remote biometric identification systems.\nThis shall not include AI "
                "systems intended to be used for biometric verification the sole purpose "
                "of which is to confirm that a specific natural person is the person he "
                "or she claims to be;"
            ),
        },
    ),
    (
        "02024R1689-20260727",
        "ita",
        "anx_XIV.sct_2.sct_a",
        {
            "label": "a)",
            "heading": "Sistemi di IA soggetti all'allegato I",
            "parent": "anx_XIV.sct_2",
            "amendments": (("inserted", "whole", "AR:1;PT:43", False),),
            "notes": 0,
            "text": (
                "Codice AIA |\nAIP 0102 | Sistemi di IA soggetti all'allegato I, sezione "
                "A, punto 2\nAIP 0103 | Sistemi di IA soggetti all'allegato I, sezione A, "
                "punto 3\nAIP 0104 | Sistemi di IA soggetti all'allegato I, sezione A, "
                "punto 4\nAIP 0105 | Sistemi di IA soggetti all'allegato I, sezione A, "
                "punto 5\nAIP 0106 | Sistemi di IA soggetti all'allegato I, sezione A, "
                "punto 6\nAIP 0107 | Sistemi di IA soggetti all'allegato I, sezione A, "
                "punto 7\nAIP 0108 | Sistemi di IA soggetti all'allegato I, sezione A, "
                "punto 8\nAIP 0109 | Sistemi di IA soggetti all'allegato I, sezione A, "
                "punto 9\nAIP 0110 | Sistemi di IA soggetti all'allegato I, sezione A, "
                "punto 10\nAIP 0111 | Sistemi di IA soggetti all'allegato I, sezione A, "
                "punto 11\nAIP 0112 | Sistemi di IA soggetti all'allegato I, sezione A, "
                "punto 12"
            ),
        },
    ),
    (
        "32026R1744",
        "eng",
        "art_1.subpara_1.point_3",
        {
            "label": "(3)",
            "heading": None,
            "parent": "art_1.subpara_1",
            "amendments": (),
            "notes": 0,
            "text": (
                "in Article 2, the following paragraph is added:\n\u201813. For high-risk AI "
                "systems referred to in Article 6(1), the application of specific "
                "requirements or obligations laid down in Articles 9 to 15 and 17 to 25 "
                "may be limited, where and to the extent that:\n(a) Union harmonisation "
                "legislation listed in Section A of Annex I lays down requirements or "
                "obligations providing an equivalent or higher level of protection of "
                "health, safety or fundamental rights as the requirement or obligation "
                "concerned; and\n(b) such limitation does not reduce the overall level of "
                "protection provided for by this Regulation.\nBy 2 August 2027, the "
                "Commission shall adopt delegated acts in accordance with Article 97 in "
                "order to supplement this Regulation by specifying the high-risk AI "
                "systems concerned, the requirements or obligations that may be limited, "
                "the conditions under which such limitation applies, and the scope of "
                "the limitation.\u2019;"
            ),
        },
    ),
]


@pytest.mark.parametrize(
    ("celex", "lang", "node_id", "expected"),
    GOLDEN,
    ids=[f"{c}-{lang}-{n}" for c, lang, n, _ in GOLDEN],
)
def test_golden_node(celex: str, lang: str, node_id: str, expected: dict[str, object]) -> None:
    doc = document(celex, lang)
    node = doc.node(f"{doc.act}/{node_id}")
    parent = node.parent.split("/")[-1] if node.parent and "/" in node.parent else node.parent
    actual: dict[str, object] = {
        "label": node.label,
        "heading": node.heading,
        "parent": parent,
        "amendments": tuple((a.action, a.scope, a.location, a.implicit) for a in node.amendments),
        "notes": len(node.notes),
    }
    if "text" in expected:
        actual["text"] = node.text
    else:
        assert node.text is not None
        lines = node.text.split("\n")
        actual |= {"first_line": lines[0], "last_line": lines[-1], "lines": len(lines)}
    assert actual == expected
