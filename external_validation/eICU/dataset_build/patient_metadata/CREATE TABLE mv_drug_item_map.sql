-- get the itemIDS for the medication list 
CREATE TABLE public.mv_drug_item_map AS
WITH all_items AS (
  SELECT
    itemid,
    label,
    LOWER(label) AS lower_label
  FROM mimiciii.d_items
  WHERE dbsource = 'metavision'
),
categorized_items AS (

SELECT
  itemid,
  label,
  CASE
    -- Crystalloids
    WHEN lower_label LIKE '%nacl%0.9%' OR
         lower_label LIKE '%dextrose%5%' OR
         lower_label LIKE '%free%water%' OR
         lower_label LIKE '%lr%' OR
         lower_label LIKE '%d5ns%' OR
         lower_label LIKE '%d5%1%2ns%' OR
         lower_label LIKE '%d5lr%' OR
         lower_label LIKE '%d5%1%4ns%' OR
         lower_label LIKE '%nacl%0.45%' OR
         lower_label LIKE '%sterile%water%' OR
         lower_label LIKE '%dextrose%10%' OR
         lower_label LIKE '%dextrose%20%' OR
         lower_label LIKE '%dextrose%30%' OR
         lower_label LIKE '%dextrose%40%' OR
         lower_label LIKE '%dextrose%50%' OR
         lower_label LIKE '%nacl%3%hypertonic%saline%' OR
         lower_label LIKE '%nacl%23.4%' 
         THEN 'crystalloids'
    -- Electrolytes
    WHEN lower_label LIKE '%potassium%chloride%' OR
         lower_label LIKE '%kcl%' OR
         lower_label LIKE '%k%phos%' OR
         lower_label LIKE '%na%phos%' OR
         lower_label LIKE '%calcium%' OR
         lower_label LIKE '%magnesium%' OR
         lower_label LIKE '%sodium%bicarbonate%' OR
         lower_label LIKE '%hydrochloric%acid%' 
         THEN 'electrolytes'
    -- Antibiotics
    WHEN lower_label LIKE '%cefepime%' OR
         lower_label LIKE '%vancomycin%' OR
         lower_label LIKE '%ceftriaxone%' OR
         lower_label LIKE '%levofloxacin%' OR
         lower_label LIKE '%azithromycin%' OR
         lower_label LIKE '%metronidazole%' OR
         lower_label LIKE '%bactrim%' OR
         lower_label LIKE '%cefazolin%' OR
         lower_label LIKE '%ciprofloxacin%' OR
         lower_label LIKE '%meropenem%' OR
         lower_label LIKE '%piperacillin%' OR
         lower_label LIKE '%tobramycin%' OR
         lower_label LIKE '%doxycycline%' OR
         lower_label LIKE '%linezolid%' OR
         lower_label LIKE '%daptomycin%' OR
         lower_label LIKE '%ceftazidime%' OR
         lower_label LIKE '%ampicillin%' OR
         lower_label LIKE '%acyclovir%' OR
         lower_label LIKE '%clindamycin%' OR
         lower_label LIKE '%aztreonam%' OR
         lower_label LIKE '%colistin%' OR
         lower_label LIKE '%amikacin%' OR
         lower_label LIKE '%imipenem%' OR
         lower_label LIKE '%rifampin%' OR
         lower_label LIKE '%erythromycin%' OR
         lower_label LIKE '%gentamicin%' OR
         lower_label LIKE '%nafcillin%' OR
         lower_label LIKE '%tamiflu%' OR
         lower_label LIKE '%penicillin%' OR
         lower_label LIKE '%quinine%' OR
         lower_label LIKE '%isoniazid%' OR
         lower_label LIKE '%ethambutol%' OR
         lower_label LIKE '%pyrazinamide%' 
         THEN 'antibiotics'
    -- Antiarrhythmics
    WHEN lower_label LIKE '%amiodarone%' OR
         lower_label LIKE '%esmolol%' OR
         lower_label LIKE '%lidocaine%' OR
         lower_label LIKE '%procainamide%' OR
         lower_label LIKE '%verapamil%' OR
         lower_label LIKE '%diltiazem%' OR
         lower_label LIKE '%adenosine%' 
         THEN 'antiarrhythmics'
    -- Anticoagulants / Antiplatelets
    WHEN lower_label LIKE '%heparin%' OR
         lower_label LIKE '%enoxaparin%' OR
         lower_label LIKE '%bivalirudin%' OR
         lower_label LIKE '%eptifibatide%' OR
         lower_label LIKE '%warfarin%' OR
         lower_label LIKE '%argatroban%' OR
         lower_label LIKE '%fondaparinux%' OR
         lower_label LIKE '%tirofiban%' OR
         lower_label LIKE '%abciximab%' OR
         lower_label LIKE '%lepirudin%' OR
         lower_label LIKE '%citrate%' OR
         lower_label LIKE '%protamine%' 
         THEN 'anticoagulants_antiplatelets'
    -- Sedatives
    WHEN lower_label LIKE '%propofol%' OR
         lower_label LIKE '%midazolam%' OR
         lower_label LIKE '%lorazepam%' OR
         lower_label LIKE '%diazepam%' OR
         lower_label LIKE '%dexmedetomidine%' OR
         lower_label LIKE '%ketamine%' OR
         lower_label LIKE '%pentobarbital%' 
         THEN 'sedatives'
    -- Analgesics
    WHEN lower_label LIKE '%fentanyl%' OR
         lower_label LIKE '%morphine%' OR
         lower_label LIKE '%hydromorphone%' OR
         lower_label LIKE '%meperidine%' OR
         lower_label LIKE '%acetaminophen%' OR
         lower_label LIKE '%methadone%' OR
         lower_label LIKE '%ketorolac%' OR
         lower_label LIKE '%naloxone%' 
         THEN 'analgesics'
    -- Neuromuscular Blockers
    WHEN lower_label LIKE '%vecuronium%' OR
         lower_label LIKE '%rocuronium%' OR
         lower_label LIKE '%cisatracurium%' OR
         lower_label LIKE '%neostigmine%' 
         THEN 'neuromuscular_blockers'
    -- GI Protection
    WHEN lower_label LIKE '%ranitidine%' OR
         lower_label LIKE '%pantoprazole%' OR
         lower_label LIKE '%famotidine%' OR
         lower_label LIKE '%lansoprazole%' OR
         lower_label LIKE '%omeprazole%' OR
         lower_label LIKE '%sucralfate%' OR
         lower_label LIKE '%esomeprazole%' 
         THEN 'gi_protection'
    -- Blood Products / Transfusions
    WHEN lower_label LIKE '%packed%red%blood%cells%' OR
         lower_label LIKE '%platelets%' OR
         lower_label LIKE '%fresh%frozen%plasma%' OR
         lower_label LIKE '%cryoprecipitate%' OR
         lower_label LIKE '%whole%blood%' OR
         lower_label LIKE '%albumin%' OR
         lower_label LIKE '%ivig%' OR
         lower_label LIKE '%factor%' OR
         lower_label LIKE '%prothrombin%' OR
         lower_label LIKE '%thrombin%' OR
         lower_label LIKE '%fibrinogen%' OR
         lower_label LIKE '%tranexamic%acid%' OR
         lower_label LIKE '%epo%' OR
         lower_label LIKE '%iron%' OR
         lower_label LIKE '%ferumoxytol%' 
         THEN 'blood_products_transfusions'
    -- Parenteral Nutrition
    WHEN lower_label LIKE '%tpn%' OR
         lower_label LIKE '%parenteral%nutrition%' OR
         lower_label LIKE '%lipids%' OR
         lower_label LIKE '%amino%acids%' OR
         lower_label LIKE '%dextrose%pn%' 
         THEN 'parenteral_nutrition'
    ELSE NULL
  END AS drug_class
FROM all_items
)
SELECT *
FROM categorized_items
WHERE drug_class IS NOT NULL; 