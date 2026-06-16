-- Active: 1770284354672@@127.0.0.1@5432@eicu
-- 1) Base: all distinct ICU stay IDS from inputevents_mv (to include also negative samples)
CREATE TABLE public.all_stays AS
SELECT DISTINCT
    patientunitstayid, 
    patienthealthsystemstayid,
    hospitalid,
    wardid,
    hospitaladmittime24,
    hospitaldischargetime24,
    unitadmittime24,
    unitdischargetime24,
    unitdischargeoffset
FROM eicu_crd.patient 
