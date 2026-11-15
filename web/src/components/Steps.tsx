import { stagger } from "../motion";

// Heart Line in five moves. Used on the welcome screen and on How it works.
const STEPS: [string, string][] = [
  ["Heart Line finds", "It reads routine cholesterol results and flags people who may have inherited high cholesterol (FH)."],
  ["A clinician confirms", "She reviews the flag and orders a genetic test."],
  ["The patient agrees", "She asks whether the programme may invite his close relatives. He can leave anyone out."],
  ["A coordinator invites", "Each adult relative gets a private invitation to a free check. Children are tested at their next Well-Child Visit."],
  ["It repeats", "A relative who has it is asked about their own family, and the same steps start again."],
];

export default function Steps() {
  return (
    <ol className="steps">
      {STEPS.map(([title, text], i) => (
        <li key={title} className="rise" style={stagger(i, 90)}>
          <strong>{title}</strong>
          <span>{text}</span>
        </li>
      ))}
    </ol>
  );
}

export const PEOPLE: { id: string; name: string; job: string; sees: string }[] = [
  { id: "clinician", name: "Dr. Layla, lipid clinician", job: "Reviews each flag, orders the test, and asks the patient about their family.", sees: "Her patients. Never a relative's result." },
  { id: "coordinator", name: "Omar, family coordinator", job: "Sends the invitations once a patient has agreed, and follows up.", sees: "Families, messages and replies." },
  { id: "nurse", name: "Hind, Well-Child nurse", job: "Adds a cholesterol test to a flagged child's next visit.", sees: "The child and the test. Nothing about the family." },
  { id: "lead", name: "Dr. Saeed, programme lead", job: "Checks that the programme works and is safe.", sees: "Numbers only. No patient names." },
];
