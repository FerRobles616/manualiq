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
    "generator_gen15": {
        "title": "Generator GEN-15 Service Manual",
        "pages": [
            [
                "1. Specifications",
                "The GEN-15 generator has a rated output of 15 kW.",
                "The generator produces 230 V single-phase and 400 V three-phase power.",
                "The operating frequency is 50 Hz.",
                "The fuel tank holds 60 liters of diesel.",
            ],
            [
                "2. Maintenance schedule",
                "Change the engine oil every 250 operating hours.",
                "Replace the oil filter every 500 operating hours.",
                "Change the coolant every 1000 operating hours.",
                "Check the battery electrolyte level every month.",
            ],
            [
                "3. Error codes and warranty",
                "E01 means low oil pressure. Stop the engine and check the oil level.",
                "E02 means high coolant temperature. Check the coolant level and radiator.",
                "E03 means generator overvoltage. Check the automatic voltage regulator.",
                "To reset the controller, turn the key to OFF and wait 30 seconds.",
                "The warranty period is 24 months for the generator.",
            ],
        ],
    },
    "steam_boiler_b90": {
        "title": "Steam Boiler B-90 Operation Manual",
        "pages": [
            [
                "1. Boiler specifications",
                "The B-90 steam boiler has a maximum working pressure of 10 bar.",
                "The maximum steam temperature is 180 °C.",
                "The water capacity is 2000 liters.",
                "The burner uses natural gas.",
            ],
            [
                "2. Operation and inspection",
                "Perform a bottom blowdown every day.",
                "Test the safety valve every week.",
                "Test the low-water cutoff every month.",
                "Have the boiler inspected annually by an authorized inspector.",
            ],
            [
                "3. Safety devices and records",
                "A low-water condition trips the burner and opens the alarm.",
                "A flame failure locks out the burner; investigate before resetting.",
                "For an emergency shutdown, close the main gas valve and press the emergency stop.",
                "Keep the boiler log for three years.",
            ],
        ],
    },
    "fire_extinguisher_sop": {
        "title": "Fire Extinguisher Inspection Procedure",
        "pages": [
            [
                "1. Inspection schedule",
                "Inspect every extinguisher visually every month.",
                "Have a professional inspection annually.",
                "Dry chemical extinguishers require maintenance every 6 years.",
                "Hydrostatic testing is required every 12 years.",
            ],
            [
                "2. Visual inspection steps",
                "Check that the pressure gauge is in the green zone.",
                "Verify the pull pin is sealed and the tamper seal is intact.",
                "Inspect the hose and nozzle for cracks or blockage.",
                "Record the inspection date and inspector name on the tag.",
            ],
            [
                "3. Pass, fail, and records",
                "Remove the extinguisher from service if the gauge is outside the green zone.",
                "A damaged hose or missing pin means the extinguisher fails inspection.",
                "Tag a failed extinguisher and place it in the red service area.",
                "Keep inspection records for five years.",
            ],
        ],
    },
    "chemical_handling_sop": {
        "title": "Chemical Handling Procedure",
        "pages": [
            [
                "1. Preparation and storage",
                "Read the safety data sheet before handling any chemical.",
                "Required PPE includes chemical goggles, nitrile gloves, and a face shield.",
                "Store chemicals in labeled containers with GHS labels.",
                "Keep incompatible chemicals in separate cabinets.",
            ],
            [
                "2. Spill response",
                "For a small spill, evacuate the area and ventilate it.",
                "Contain the spill with absorbent material and place it in a labeled "
                "waste container.",
                "For a large spill, call emergency services and do not attempt cleanup.",
                "Report every spill to the supervisor.",
            ],
            [
                "3. Exposure, training, and waste",
                "Use the eyewash station for at least 15 minutes after eye contact.",
                "Train employees on chemical handling every year.",
                "Dispose of chemical waste through the approved hazardous waste vendor.",
                "Keep the SDS accessible for every chemical in the work area.",
            ],
        ],
    },
    "electrical_panel_sop": {
        "title": "Electrical Panel Maintenance Procedure",
        "pages": [
            [
                "1. Scope and PPE",
                "The procedure applies to panels energized at 50 volts or more.",
                "Required PPE includes arc-rated clothing, a face shield, and "
                "voltage-rated gloves.",
                "Only qualified electricians may open an energized panel.",
            ],
            [
                "2. Isolation and inspection",
                "De-energize and lock out the panel before removing covers.",
                "Verify zero voltage with a meter rated for the panel voltage.",
                "Inspect busbars and terminals for discoloration or overheating.",
                "Tighten terminal connections to 20 Nm.",
            ],
            [
                "3. Thermal scan and repairs",
                "Perform a thermal scan of the panel annually.",
                "A hot spot above 20 °C over ambient requires investigation.",
                "Record the thermal scan results in the maintenance log.",
                "Replace damaged breakers with the same voltage and current rating.",
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
