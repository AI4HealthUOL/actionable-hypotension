-- alles von map und nur die schnittmenge von hr die 2 werte haben

drop table if exists evaluation.merged_mix_hr_dataset

CREATE TABLE evaluation.merged_mix_hr_dataset as
Select 
m.*,
hr.hr_mean,
hr.hr_median,
hr.hr_std,
hr.hr_iqr,
hr.hr_first,
hr.hr_last,
hr.hr_slope,
(hr.hr_mean IS NULL) AS hr_missing,
hr.hr_only_2_values
from ce_approach.merged_mix_features m 
left join evaluation.hr_windows_statistical_features hr 
on hr.icustay_id = m.icustay_id
and hr.context_start = m.context_start
 


select * from evaluation.merged_mix_hr_dataset where hr_last is null