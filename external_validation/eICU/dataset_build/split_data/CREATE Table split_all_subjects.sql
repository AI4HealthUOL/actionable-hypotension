-- The context: Our datasets have a different amount of subject_ids in them. So they are not so straight forward comparable
-- all_mv_labeled_windows has 17678 unique subject ids
		-- mix_windows has unique subject ids 17655 
		-- invasive windows has unique subject ids 8986
		-- noninvasive windows has unique subject ids 17285
--Idea: 
-- We create one table that lists all distinct subject ids across our three datasets and we split all of them 70/15/15.
-- Then we ensure that subject ids will end up in the same splits across the datasets. So in invasive_windows, the test split might contain 
-- fewer subject_ids than 15%, simply because those subject_ids don’t exist in that dataset.
-- The datasets still use consistents plits though. The sizes of splits wont be exactly 70/15/15 in each dataset
-- which seems to be okay if our goal is comparability across datasets. 



-- We use the same logic of splitting the data patientwise into train/val/test using a 70/15/15 split as in CREATE TABLE dataset.sql 
-- From CREATE TABLE dataset.sql But we create a new table that uses this logic for all existing subject ids across our datasets.
CREATE TABLE public.split_all_admissions AS
SELECT 
  patienthealthsystemstayid,
  CASE
    WHEN ( ('x'||substr(md5(patienthealthsystemstayid::text),1,8))::bit(32)::bigint % 100 ) < 70 THEN 'train'
    WHEN ( ('x'||substr(md5(patienthealthsystemstayid::text),1,8))::bit(32)::bigint % 100 ) < 85 THEN 'val'
    ELSE 'test'
  END AS split
FROM (
  SELECT DISTINCT patienthealthsystemstayid FROM public.mix_windows
) AS unique_admissions;