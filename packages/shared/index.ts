export const recognitionStates = [
  "no_face",
  "multiple_faces_rejected",
  "quality_rejected",
  "spoof_rejected",
  "unknown",
  "ambiguous",
  "candidate_tracking",
  "duplicate",
  "attendance_marked",
] as const;

export type RecognitionState = (typeof recognitionStates)[number];

export const roleLabels = ["superadmin", "admin", "reviewer", "viewer"] as const;
export type RoleLabel = (typeof roleLabels)[number];

