from pathlib import Path

from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data" / "corpus"

DOCUMENTS = {
    "hydraulic_press_h200": {
        "title": "Hydraulic Press H-200 Service Manual",
        "pages": [
            [
                "1. Safety and specifications",
                "The H-200 hydraulic press is designed for cold metal forming.",
                "The maximum operating pressure is 180 bar.",
                "The hydraulic reservoir uses ISO VG 46 mineral oil.",
                "Always wear safety glasses and steel-toed boots when operating the press.",
            ],
            [
                "2. Maintenance schedule",
                "Change the hydraulic oil every 500 operating hours.",
                "Replace the oil filter every 250 operating hours.",
                "Inspect hoses and fittings every 100 operating hours.",
                "Lubricate the guide rails every 50 operating hours with lithium grease.",
            ],
            [
                "3. Troubleshooting and warranty",
                "If pressure drops below 120 bar, inspect the pressure relief valve first.",
                "An abnormal knocking noise usually indicates air in the hydraulic oil; "
                "bleed the system.",
                "The press frame bolts require 120 Nm of torque.",
                "The warranty period is 24 months for the frame and 12 months for "
                "hydraulic components.",
            ],
        ],
    },
    "hvac_cx40": {
        "title": "HVAC CX-40 Service Manual",
        "pages": [
            [
                "1. Unit specifications",
                "The CX-40 rooftop unit uses R-410A refrigerant.",
                "The factory refrigerant charge is 2.4 kg.",
                "The supply airflow is 1200 CFM.",
                "The return air filter is MERV 13.",
            ],
            [
                "2. Preventive maintenance",
                "Replace the air filter every 3 months.",
                "Clean the evaporator coil every 6 months.",
                "Flush the condensate drain every 3 months.",
                "Check the refrigerant pressure in both heating and cooling seasons.",
            ],
            [
                "3. Error codes and reset",
                "E1 means high-pressure lockout. Check condenser airflow and the outdoor fan.",
                "E2 means low-pressure lockout. Check refrigerant charge and evaporator airflow.",
                "E3 means sensor fault. Replace the discharge temperature sensor.",
                "To reset the unit, turn the thermostat off for 30 seconds, then back on.",
            ],
        ],
    },
    "loto_procedure": {
        "title": "Lockout Tagout Procedure",
        "pages": [
            [
                "1. Scope and personal protective equipment",
                "This procedure applies to equipment energized at 50 volts or more.",
                "Required PPE: arc-rated face shield, voltage-rated gloves, safety glasses, "
                "and flame-resistant clothing.",
                "Only authorized employees may apply locks and tags.",
            ],
            [
                "2. Lockout sequence and inspection",
                "Steps: notify affected employees, shut down the equipment, isolate all "
                "energy sources, apply locks and tags, release stored energy, and verify "
                "zero energy.",
                "Try to start the equipment after lockout to verify isolation.",
                "Remove locks only by the employee who applied them.",
                "Inspect the lockout procedure annually.",
            ],
        ],
    },
    "forklift_fl30": {
        "title": "Forklift FL-30 Service Manual",
        "pages": [
            [
                "1. Capacity and specifications",
                "The FL-30 forklift has a rated lifting capacity of 3000 kg.",
                "The traction battery is 48 V.",
                "The maximum lift height is 6 meters.",
                "The forklift uses solid pneumatic tires.",
                "Operators must wear a hard hat and a high-visibility vest.",
            ],
            [
                "2. Maintenance schedule",
                "Check the battery water level every week.",
                "Inspect the service brakes every 250 operating hours.",
                "Change the hydraulic oil every 1000 operating hours.",
                "Lubricate the mast chains every 50 operating hours.",
            ],
            [
                "3. Error codes and emergency procedure",
                "E01 means low battery voltage. Charge the battery.",
                "E02 means motor overheat. Stop the forklift and let it cool.",
                "E03 means low hydraulic pressure. Check the hydraulic lines.",
                "To lower the forks in an emergency, pull the emergency lowering valve.",
                "The warranty period is 18 months for the frame.",
            ],
        ],
    },
    "air_compressor_ac75": {
        "title": "Air Compressor AC-75 Service Manual",
        "pages": [
            [
                "1. Specifications",
                "The AC-75 compressor has a 75 kW motor.",
                "The maximum discharge pressure is 10 bar.",
                "The free air delivery is 500 CFM.",
                "Use ISO VG 46 compressor oil.",
            ],
            [
                "2. Maintenance",
                "Change the compressor oil every 2000 operating hours.",
                "Replace the oil filter every 500 operating hours.",
                "Drain the condensate from the receiver tank daily.",
                "Inspect the drive belt every 250 operating hours.",
            ],
            [
                "3. Troubleshooting and warranty",
                "High discharge temperature usually means a blocked oil cooler.",
                "A pressure drop usually means a leak in the air line.",
                "To reset the compressor, press the red reset button for five seconds.",
                "The warranty period is 24 months for the compressor unit.",
            ],
        ],
    },
    "confined_space_sop": {
        "title": "Confined Space Entry Procedure",
        "pages": [
            [
                "1. Permit and atmospheric limits",
                "A confined space entry permit is required before entry.",
                "The acceptable oxygen range is 19.5% to 23.5%.",
                "Test for flammable gas and hydrogen sulfide before entry.",
                "Required PPE includes a full-face respirator, gloves, and a safety harness.",
            ],
            [
                "2. Entry and rescue",
                "Isolate and lock out all energy sources before entry.",
                "Ventilate the space and retest the atmosphere before entry.",
                "A standby attendant must remain outside the space during entry.",
                "If a worker collapses, call emergency services and use the tripod rescue system.",
            ],
            [
                "3. Communication, evacuation, and records",
                "Maintain continuous communication with the attendant.",
                "Evacuate immediately if the gas monitor alarms.",
                "Keep the entry permit for one year after the work.",
                "Retrain entrants and attendants every year.",
            ],
        ],
    },
}


def build_document(slug: str, title: str, pages: list[list[str]]) -> None:
    path = OUTPUT_DIR / f"{slug}.pdf"
    document = SimpleDocTemplate(str(path), title=title)
    styles = getSampleStyleSheet()
    story = []

    for page_index, paragraphs in enumerate(pages):
        if page_index == 0:
            story.append(Paragraph(title, styles["Title"]))
        for paragraph in paragraphs:
            if paragraph[0].isdigit() and "." in paragraph[:3]:
                story.append(Paragraph(paragraph, styles["Heading2"]))
            else:
                story.append(Paragraph(paragraph, styles["BodyText"]))
        if page_index < len(pages) - 1:
            story.append(PageBreak())

    document.build(story)
    print(f"wrote {path}")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for slug, spec in DOCUMENTS.items():
        build_document(slug, spec["title"], spec["pages"])


if __name__ == "__main__":
    main()
