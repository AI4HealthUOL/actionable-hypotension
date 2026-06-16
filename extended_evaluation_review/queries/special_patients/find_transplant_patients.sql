#transplant V42, V43 in d_icd_procedures
# stroke: 433, 434, 436
# brain injury: 959.01, 850.1 – 850.5, 850.9, 851.0 – 854.1, 803.0 – 804.9, 800.0 – 801.9, 800.0 – 801.9, 803.0 – 804.9, 850.1 – 850.5, 850.9, 851.0 – 854.1, 959.01  https://cdn-links.lww.com/permalink/neu/a/neu_71_6_2012_09_24_carroll_201959_sdc1.pdf
# hirnblutung: 430, 431, 432, 800.2 – 800.3, 800.7 – 800.8, 801.2 – 801.3, 801.7 – 801.8, 803.2 – 803.3,
803.7 – 803.8, 804.2 – 804.3, 804.7 – 804.8, 852.0 – 853.1

# table with columns: subject id, transplant (0/1), stroke (0/1), brain_injury (0/1), brain hemoorhage (0/1)
"""
the relevant question is: is this condition the primary driver of the ICU stay? A patient admitted post-liver-transplant is on 
norepinephrine because of the transplant physiology, immunosuppression, 
and post-surgical vasodilation — not because of the kind of spontaneous instability your model is trained to predict.
"""



CREATE TABLE evaluation.exclusion_criteria AS
SELECT
    ie.subject_id
    , ie.hadm_id
    , ie.icustay_id
    -- Transplant: V42.x, V43.x in procedures
    , MAX(CASE WHEN (pr.icd9_code IN (
    '5051', '5052', '5053', '5054', '5059',  -- kidney transplant
    '5151', '5159',                            -- liver transplant  
    '3750', '3751', '3752', '3754',            -- heart transplant
    '3350',                                    -- lung transplant
    '5280', '5282'                             -- pancreas transplant
    ) 
    OR (pr.icd9_code LIKE '410%')) -- bone marrow transplant
    THEN 1 ELSE 0 END) AS transplant
    -- Stroke: 433.x, 434.x, 436.x in diagnoses
    , MAX(CASE WHEN dx.icd9_code LIKE '433%' OR dx.icd9_code LIKE '434%'
                 OR dx.icd9_code LIKE '436%'
               THEN 1 ELSE 0 END) AS stroke
    -- Brain injury (per Carroll 2012 supplement)
    , MAX(CASE WHEN
            dx.icd9_code = '95901'
         OR dx.icd9_code BETWEEN '8501' AND '8505'
         OR dx.icd9_code = '8509'
         OR dx.icd9_code BETWEEN '8510' AND '8541'
         OR dx.icd9_code BETWEEN '8030' AND '8049'
         OR dx.icd9_code BETWEEN '8000' AND '8019'
         OR dx.icd9_code BETWEEN '8032' AND '8049'
               THEN 1 ELSE 0 END) AS brain_injury
    -- Brain hemorrhage: 430, 431, 432 + fracture codes with hemorrhage
    , MAX(CASE WHEN
            dx.icd9_code LIKE '430%'
         OR dx.icd9_code LIKE '431%'
         OR dx.icd9_code LIKE '432%'
         OR dx.icd9_code BETWEEN '8002' AND '8003'
         OR dx.icd9_code BETWEEN '8007' AND '8008'
         OR dx.icd9_code BETWEEN '8012' AND '8013'
         OR dx.icd9_code BETWEEN '8017' AND '8018'
         OR dx.icd9_code BETWEEN '8022' AND '8023'
         OR dx.icd9_code BETWEEN '8027' AND '8028'
         OR dx.icd9_code BETWEEN '8032' AND '8033'
         OR dx.icd9_code BETWEEN '8037' AND '8038'
         OR dx.icd9_code BETWEEN '8042' AND '8043'
         OR dx.icd9_code BETWEEN '8047' AND '8048'
         OR dx.icd9_code BETWEEN '8520' AND '8531'
               THEN 1 ELSE 0 END) AS brain_hemorrhage
FROM mimiciii.icustays ie
LEFT JOIN mimiciii.diagnoses_icd dx
    ON ie.subject_id = dx.subject_id AND ie.hadm_id = dx.hadm_id AND dx.seq_num <= 3
LEFT JOIN mimiciii.procedures_icd pr
    ON ie.subject_id = pr.subject_id AND ie.hadm_id = pr.hadm_id
GROUP BY ie.subject_id, ie.hadm_id, ie.icustay_id
ORDER BY ie.subject_id, ie.hadm_id, ie.icustay_id;