CREATE INDEX idx_filtered_maps_patient_offset 
ON public.filtered_maps (patientunitstayid, "offset" DESC);

CREATE INDEX idx_catecholamine_patient_offset
ON public.catecholamine_events_4h (patientunitstayid, infusionoffset);

CREATE INDEX idx_windows_positive
ON public.all_labeled_windows (positive_event)
WHERE positive_event = true;