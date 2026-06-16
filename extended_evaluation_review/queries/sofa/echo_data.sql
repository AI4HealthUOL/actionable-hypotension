-- THIS SCRIPT IS AUTOMATICALLY GENERATED. DO NOT EDIT IT DIRECTLY.
CREATE TABLE evaluation.echo_data AS 
-- This code extracts structured data from echocardiographies
-- You can join it to the text notes using ROW_ID
-- Just note that ROW_ID will differ across versions of MIMIC-III.
select ROW_ID
  , subject_id, hadm_id
  , chartdate
  -- charttime is always null for echoes..
  -- however, the time is available in the echo text, e.g.:
  -- , substring(ne.text, 'Date/Time: [\[\]0-9*-]+ at ([0-9:]+)') as TIMESTAMP
  -- we can therefore impute it and re-create charttime
  , TO_TIMESTAMP(
      TO_CHAR(chartdate, 'YYYY-MM-DD') 
      || substring(ne.text, 'Date/Time: .+? at ([0-9]+:[0-9]{2})')
      || ':00',
      'YYYY-MM-DDHH24:MI:SS'
   ) AS charttime
  -- explanation of below substring:
  --  'Indication: ' - matched verbatim
  --  (.*?) - match any character
  --  \n - the end of the line
  -- substring only returns the item in ()s
  -- note: the '?' makes it non-greedy. if you exclude it, it matches until it reaches the *last* \n

  , substring(ne.text, 'Indication: (.*?)\n') as Indication
  -- sometimes numeric values contain de-id text, e.g. [** Numeric Identifier **]
  -- this removes that text
  , cast(substring(ne.text, 'Height: \\x28in\\x29 ([0-9]+)') as numeric) as Height
  , cast(substring(ne.text, 'Weight \\x28lb\\x29: ([0-9]+)\n') as numeric) as Weight
  , cast(substring(ne.text, 'BSA \\x28m2\\x29: ([0-9]+) m2\n') as numeric) as BSA -- ends in 'm2'
  , substring(ne.text, 'BP \\x28mm Hg\\x29: (.+)\n') as BP -- Sys/Dias
  , cast(substring(ne.text, 'BP \\x28mm Hg\\x29: ([0-9]+)/[0-9]+?\n') as numeric) as BPSys -- first part of fraction
  , cast(substring(ne.text, 'BP \\x28mm Hg\\x29: [0-9]+/([0-9]+?)\n') as numeric) as BPDias -- second part of fraction
  , cast(substring(ne.text, 'HR \\x28bpm\\x29: ([0-9]+?)\n') as numeric) as HR

  , substring(ne.text, 'Status: (.*?)\n') as Status
  , substring(ne.text, 'Test: (.*?)\n') as Test
  , substring(ne.text, 'Doppler: (.*?)\n') as Doppler
  , substring(ne.text, 'Contrast: (.*?)\n') as Contrast
  , substring(ne.text, 'Technical Quality: (.*?)\n') as TechnicalQuality
FROM mimiciii.noteevents ne
where category = 'Echo';
