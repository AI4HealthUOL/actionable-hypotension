-- get the itemIDS for the medication list 

# first create a look up table similar to d_items
Drop table if exists public.eicu_all_drugs

CREATE TABLE public.eicu_all_drugs AS
SELECT DISTINCT
    medicationid AS infusiondrugid_medicationid,
    LOWER(drugname) AS lower_drugname,
    'medication' AS source
FROM eicu_crd.medication
WHERE drugname IS NOT NULL
UNION
SELECT DISTINCT
    infusiondrugid AS infusiondrugid_medicationid,
    LOWER(drugname) AS lower_drugname,
    'infusiondrug' AS source
FROM eicu_crd.infusiondrug
WHERE drugname IS NOT NULL;

DROP table if exists public.eicu_drug_item_map

# then categorize the medications/drug_ivs into our drug_classes ( contains duplicates still ) 
CREATE TABLE public.eicu_drug_item_map AS
WITH categorized_items AS (
SELECT DISTINCT
  lower_drugname as label,
  CASE
    -- Crystalloids
    WHEN lower_drugname LIKE '%nacl%0.9%' OR
         lower_drugname LIKE '%dextrose%5%' OR
         lower_drugname LIKE '%free%water%' OR
         lower_drugname LIKE '%lr%' OR
         lower_drugname LIKE '%d5ns%' OR
         lower_drugname LIKE '%d5%1%2ns%' OR
         lower_drugname LIKE '%d5lr%' OR
         lower_drugname LIKE '%d5%1%4ns%' OR
         lower_drugname LIKE '%nacl%0.45%' OR
         lower_drugname LIKE '%sterile%water%' OR
         lower_drugname LIKE '%dextrose%10%' OR
         lower_drugname LIKE '%dextrose%20%' OR
         lower_drugname LIKE '%dextrose%30%' OR
         lower_drugname LIKE '%dextrose%40%' OR
         lower_drugname LIKE '%dextrose%50%' OR
         lower_drugname LIKE '%nacl%3%hypertonic%saline%' OR
         lower_drugname LIKE '%nacl%23.4%' 
         THEN 'crystalloids'
    -- Electrolytes
    WHEN lower_drugname LIKE '%potassium%chloride%' OR
         lower_drugname LIKE '%kcl%' OR
         lower_drugname LIKE '%k%phos%' OR
         lower_drugname LIKE '%na%phos%' OR
         lower_drugname LIKE '%calcium%' OR
         lower_drugname LIKE '%magnesium%' OR
         lower_drugname LIKE '%sodium%bicarbonate%' OR
         lower_drugname LIKE '%hydrochloric%acid%' 
         THEN 'electrolytes'
    -- Antibiotics
    WHEN lower_drugname LIKE '%cefepime%' OR
         lower_drugname LIKE '%vancomycin%' OR
         lower_drugname LIKE '%ceftriaxone%' OR
         lower_drugname LIKE '%levofloxacin%' OR
         lower_drugname LIKE '%azithromycin%' OR
         lower_drugname LIKE '%metronidazole%' OR
         lower_drugname LIKE '%bactrim%' OR
         lower_drugname LIKE '%cefazolin%' OR
         lower_drugname LIKE '%ciprofloxacin%' OR
         lower_drugname LIKE '%meropenem%' OR
         lower_drugname LIKE '%piperacillin%' OR
         lower_drugname LIKE '%tobramycin%' OR
         lower_drugname LIKE '%doxycycline%' OR
         lower_drugname LIKE '%linezolid%' OR
         lower_drugname LIKE '%daptomycin%' OR
         lower_drugname LIKE '%ceftazidime%' OR
         lower_drugname LIKE '%ampicillin%' OR
         lower_drugname LIKE '%acyclovir%' OR
         lower_drugname LIKE '%clindamycin%' OR
         lower_drugname LIKE '%aztreonam%' OR
         lower_drugname LIKE '%colistin%' OR
         lower_drugname LIKE '%amikacin%' OR
         lower_drugname LIKE '%imipenem%' OR
         lower_drugname LIKE '%rifampin%' OR
         lower_drugname LIKE '%erythromycin%' OR
         lower_drugname LIKE '%gentamicin%' OR
         lower_drugname LIKE '%nafcillin%' OR
         lower_drugname LIKE '%tamiflu%' OR
         lower_drugname LIKE '%penicillin%' OR
         lower_drugname LIKE '%quinine%' OR
         lower_drugname LIKE '%isoniazid%' OR
         lower_drugname LIKE '%ethambutol%' OR
         lower_drugname LIKE '%pyrazinamide%' 
         THEN 'antibiotics'
    -- Antiarrhythmics
    WHEN lower_drugname LIKE '%amiodarone%' OR
         lower_drugname LIKE '%esmolol%' OR
         lower_drugname LIKE '%lidocaine%' OR
         lower_drugname LIKE '%procainamide%' OR
         lower_drugname LIKE '%verapamil%' OR
         lower_drugname LIKE '%diltiazem%' OR
         lower_drugname LIKE '%adenosine%' 
         THEN 'antiarrhythmics'
    -- Anticoagulants / Antiplatelets
    WHEN lower_drugname LIKE '%heparin%' OR
         lower_drugname LIKE '%enoxaparin%' OR
         lower_drugname LIKE '%bivalirudin%' OR
         lower_drugname LIKE '%eptifibatide%' OR
         lower_drugname LIKE '%warfarin%' OR
         lower_drugname LIKE '%argatroban%' OR
         lower_drugname LIKE '%fondaparinux%' OR
         lower_drugname LIKE '%tirofiban%' OR
         lower_drugname LIKE '%abciximab%' OR
         lower_drugname LIKE '%lepirudin%' OR
         lower_drugname LIKE '%citrate%' OR
         lower_drugname LIKE '%protamine%' 
         THEN 'anticoagulants_antiplatelets'
    -- Sedatives
    WHEN lower_drugname LIKE '%propofol%' OR
         lower_drugname LIKE '%midazolam%' OR
         lower_drugname LIKE '%lorazepam%' OR
         lower_drugname LIKE '%diazepam%' OR
         lower_drugname LIKE '%dexmedetomidine%' OR
         lower_drugname LIKE '%ketamine%' OR
         lower_drugname LIKE '%pentobarbital%' 
         THEN 'sedatives'
    -- Analgesics
    WHEN lower_drugname LIKE '%fentanyl%' OR
         lower_drugname LIKE '%morphine%' OR
         lower_drugname LIKE '%hydromorphone%' OR
         lower_drugname LIKE '%meperidine%' OR
         lower_drugname LIKE '%acetaminophen%' OR
         lower_drugname LIKE '%methadone%' OR
         lower_drugname LIKE '%ketorolac%' OR
         lower_drugname LIKE '%naloxone%' 
         THEN 'analgesics'
    -- Neuromuscular Blockers
    WHEN lower_drugname LIKE '%vecuronium%' OR
         lower_drugname LIKE '%rocuronium%' OR
         lower_drugname LIKE '%cisatracurium%' OR
         lower_drugname LIKE '%neostigmine%' 
         THEN 'neuromuscular_blockers'
    -- GI Protection
    WHEN lower_drugname LIKE '%ranitidine%' OR
         lower_drugname LIKE '%pantoprazole%' OR
         lower_drugname LIKE '%famotidine%' OR
         lower_drugname LIKE '%lansoprazole%' OR
         lower_drugname LIKE '%omeprazole%' OR
         lower_drugname LIKE '%sucralfate%' OR
         lower_drugname LIKE '%esomeprazole%' 
         THEN 'gi_protection'
    -- Blood Products / Transfusions
    WHEN lower_drugname LIKE '%packed%red%blood%cells%' OR
         lower_drugname LIKE '%platelets%' OR
         lower_drugname LIKE '%fresh%frozen%plasma%' OR
         lower_drugname LIKE '%cryoprecipitate%' OR
         lower_drugname LIKE '%whole%blood%' OR
         lower_drugname LIKE '%albumin%' OR
         lower_drugname LIKE '%ivig%' OR
         lower_drugname LIKE '%factor%' OR
         lower_drugname LIKE '%prothrombin%' OR
         lower_drugname LIKE '%thrombin%' OR
         lower_drugname LIKE '%fibrinogen%' OR
         lower_drugname LIKE '%tranexamic%acid%' OR
         lower_drugname LIKE '%epo%' OR
         lower_drugname LIKE '%iron%' OR
         lower_drugname LIKE '%ferumoxytol%' 
         THEN 'blood_products_transfusions'
    -- Parenteral Nutrition
    WHEN lower_drugname LIKE '%tpn%' OR
         lower_drugname LIKE '%parenteral%nutrition%' OR
         lower_drugname LIKE '%lipids%' OR
         lower_drugname LIKE '%amino%acids%' OR
         lower_drugname LIKE '%dextrose%pn%' 
         THEN 'parenteral_nutrition'
    ELSE NULL
  END AS drug_class,
  source
FROM public.eicu_all_drugs
)
SELECT *
FROM categorized_items
WHERE drug_class IS NOT NULL; 