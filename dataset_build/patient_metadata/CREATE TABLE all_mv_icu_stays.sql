-- Active: 1768480900465@@localhost@5432@mimic
-- 1) Base: all distinct ICU stay IDS from inputevents_mv (to include also negative samples)
CREATE TABLE ce_approach.all_mv_icu_stays AS
SELECT DISTINCT
    i.subject_id, 
    i.hadm_id, 
    imv.icustay_id, 
    i.intime as icu_intime, 
    i.outtime as icu_outtime
FROM mimiciii.inputevents_mv imv
JOIN mimiciii.icustays i 
    ON imv.icustay_id = i.icustay_id