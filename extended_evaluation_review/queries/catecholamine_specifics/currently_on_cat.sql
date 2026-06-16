"""-
linkorder_treatment_events with columns icustay id treatment_start and treatment_end
for each row in all_mv_context_target_windows, check if context end lies between (context_end == treatment starttime also counts as currently on cat) 
treatment_starttime and treatment_endtime since context end is our prediction time"""

CREATE TABLE evaluation.currently_on AS 
SELECT 
  m.subject_id,
  m.icustay_id,
  m.hadm_id,
  m.context_start,
  m.context_end,
  CASE WHEN EXISTS (
    SELECT 1
    FROM ce_approach.linkorder_treatment_events t
    WHERE t.icustay_id = m.icustay_id
      AND t.treatment_starttime <= m.context_end
      AND t.treatment_endtime   > m.context_end
  )
  THEN 1 ELSE 0 END AS currently_on_cat
FROM all_mv_context_target_windows m;


-- add as feature to main dataset and hr_main_dataset


Create Table evaluation.merged_mix_features_w_cat_status as
select 
m.*,
c.currently_on_cat
from ce_approach.merged_mix_features m 
left join evaluation.currently_on c on 
m.icustay_id = c.icustay_id
and m.context_start = c.context_start 


drop table if exists evaluation.merged_mix_hr_w_cat_status_dataset

Create Table evaluation.merged_mix_hr_w_cat_status_dataset as
select 
m.*,
c.currently_on_cat
from evaluation.merged_mix_hr_dataset m 
left join evaluation.currently_on c on 
m.icustay_id = c.icustay_id
and m.context_start = c.context_start 

