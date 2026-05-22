"""-
linkorder_treatment_events with columns icustay id treatment_start and treatment_end
for each row in all_mv_context_target_windows, check if context end lies between (context_end == treatment starttime also counts as currently on cat) 
treatment_starttime and treatment_endtime since context end is our prediction time"""

drop table if exists evaluation.cat_labels

CREATE TABLE evaluation.cat_labels AS 
SELECT 
  m.subject_id,
  m.icustay_id,
  m.context_start,
  m.context_end,
  t.label as cat_label,
  t.treatment_starttime,
  t.treatment_endtime
FROM ce_approach.merged_mix_features m
JOIN ce_approach.linkorder_treatment_events t
  ON t.icustay_id = m.icustay_id
 AND t.treatment_starttime >= m.context_end
 AND t.treatment_starttime <=  m.context_end + INTERVAL '15 minutes'
WHERE m.positive_event = True;


-- add as feature to main dataset 
drop table if exists evaluation.merged_mix_features_w_cat_status_w_label

Create Table evaluation.merged_mix_features_w_cat_status_w_label as
select 
m.*,
c.currently_on_cat,
COALESCE(l.cat_label, 'negative') AS cat_label
from ce_approach.merged_mix_features m 
left join evaluation.currently_on c on 
m.icustay_id = c.icustay_id
and m.context_start = c.context_start 
left join evaluation.cat_labels l on 
m.icustay_id = l.icustay_id
and m.context_start = l.context_start

--and hr_main_dataset
drop table if exists evaluation.merged_mix_hr_w_cat_status_dataset

Create Table evaluation.merged_mix_hr_w_cat_status_dataset as
select 
m.*,
c.currently_on_cat
from evaluation.merged_mix_hr_dataset m 
left join evaluation.currently_on c on 
m.icustay_id = c.icustay_id
and m.context_start = c.context_start 

