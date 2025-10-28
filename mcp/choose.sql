-- Part of the Magic machinery, to be moved into the Go library.
CREATE OR REPLACE FUNCTION alloydb_ai_nl.choose_prompt_template(
  check_intent BOOL DEFAULT FALSE) RETURNS text AS $$
DECLARE
  prompt TEXT;
BEGIN
  prompt := E'Use one of the following templates to generate the output for [My Question]:\n\n';
  prompt := prompt || E'  [My Question]: {nl_question}\n\n';
  prompt := prompt || E'Let''s think step by step to finish this task:\n';
  prompt := prompt || E'Step 1) Find a [Template] with a [Manifest] that has the same intent as [My Question].\n';
  prompt := prompt || E'Step 2) If you found the [Template], identify [Parameter values] in [My Question] by analyzing \n';
  prompt := prompt || E'        the [Question] and [Manifest] in the identified template, and its [Example].\n';
  prompt := prompt || E'Step 3) If you found the [Parameter values], replace the parameters in the [Paramertrized SQL] \n';
  prompt := prompt || E'        to produce final answer.\n\nYour MUST follow these rules carefully:\n';
  prompt := prompt || E'Rule 1) Use ONLY the template with the [Manifest] that captures the core intent \n';
  prompt := prompt || E'        and entities in [My Question], and with a [Question] similar to [My Question].\n';
  prompt := prompt || E'Rule 2) It is OK if the parameter (or parameters) in [My Qyestion] and the [Question] \n';
  prompt := prompt || E'        in the template chosen do not match exactly. The intent match matters the most.\n';
  prompt := prompt || E'Rule 3) If you have any doubt whether a [Manifest] has the same intent as [My Question], \n';
  prompt := prompt || E'        output the result as JSON dictionary \n';
  prompt := prompt || E'        { "answer" : "I don''t know" , "dbg" : "Manifest does not have the same intent" }, \n';
  prompt := prompt || E'        wrapped by triple backticks in markdown style.\n';
  prompt := prompt || E'Rule 4) Only when there is one [Template] with the [Manifest] that exactly matches [My Question]\n';
  prompt := prompt || E'        without modifying the [Manifest], output the result as a JSON dictionary with six keys,\n';
  prompt := prompt || E'        "answer", "manifest", "intent", "intent_match", "mismatch_reason", "dbg".\n';
  prompt := prompt || E'        The value corresponding to the key "answer" is a SQL statement, where the parameters\n';
  prompt := prompt || E'        in the [Paramertrized SQL] in the selected [Template] are replaced with the detected values.\n';
  prompt := prompt || E'        The value corresponding to the key "manifest" is the [Manifest] of the chosen [Template].\n';
  prompt := prompt || E'        The value corresponding to the key "intent" is the [Parameterized Intent] of the chosen [Template], \n';
  prompt := prompt || E'        with the parameters replaced with the detected values. When comparing with strings, use\n';
  prompt := prompt || E'        single quotes around the strings, NOT double quotes.\n';
  IF check_intent THEN
    prompt := prompt || E'Rule 5) IF [My Question] is answerable by the generated "answer" and [My Question]\n';
    prompt := prompt || E'        has the same intent as "intent", then set "intent_match" to true, set\n';
    prompt := prompt || E'        "mismatch_reason" to empty string, and set "dbg" to "Matching template found.".\n';
    prompt := prompt || E'        ELSE, set "intent_match" to false and set "mismatch_reason" to the reason\n';
    prompt := prompt || E'        that [My Question] is NOT answerable by the generated "answer" OR there is\n';
    prompt := prompt || E'        a mismatch between the intent of [My Question] and the generated "intent",\n';
    prompt := prompt || E'        and set the value for "dbg" "Matching template not found.".\n';
  ELSE
    prompt := prompt || E'Rule 5) Skip checking intent, and set "intent_match" to empty string and "mismatch_reason" \n';
    prompt := prompt || E'        to "skipped", and "set the value for dbg" equal to "Skipped intent check".\n';
  END IF;
  prompt := prompt || E'Rule 6) IF none of the provided templates have a [Manifest] that exactly matches the criteria \n';
  prompt := prompt || E'        outlined in [Rule 4], output the result as JSON dictionary \n';
  prompt := prompt || E'        { "answer" : "I don''t know", "dbg" : "There is no matching template."},\n';
  prompt := prompt || E'        wrapped by triple backticks in markdown style.\n\n';
  RETURN prompt;
END;
$$ LANGUAGE plpgsql;

-- Part of the Magic machinery, to be moved into the Go library.
CREATE OR REPLACE FUNCTION alloydb_ai_nl.choose_prompt_template_fragments(
  check_intent BOOL DEFAULT FALSE) RETURNS text AS $$
DECLARE
  prompt TEXT;
BEGIN
  prompt := E'You will produce [output] (a JSON dictionary) to answer [My Question]:\n';
  prompt := prompt || E'  [My Question]: {nl_question}\n\n';
  prompt := prompt || E'  [My Manifest]: {nl_manifest}\n\n';
  prompt := prompt || E'The [output] is a JSON dictionary with 6 keys, "answer", "manifest",\n';
  prompt := prompt || E'"intent", "intent_match", "mismatch_reason", and "dbg". To produce [output],\n';
  prompt := prompt || E'you will first apply [Step 1] which generates [SQL1], [Intent1], and [Manifest1]. \n';
  prompt := prompt || E'IF [SQL1] is "", then set the [output] to the JSON dictionary \n';
  prompt := prompt || E'{ "answer" : "I don''t know", "dbg" : "[SQL1] is empty" }, wrapped\n';
  prompt := prompt || E'by triple backticks in markdown style.\n';

  prompt := prompt || E'ELSE, [Step 2] generates [SQL2], [Intent2], and [Manifest2], respectively, from \n';
  prompt := prompt || E'[SQL1], [Intent1], and [Manifest1]  as input. IF the produced [SQL2] is "", \n';
  prompt := prompt || E'then set the [output] to the JSON dictionary \n';
  prompt := prompt || E'{ "answer" : "I don''t know", "dbg" : "[SQL2] is empty." }, wrapped \n';
  prompt := prompt || E'by triple backticks in markdown style.\n';

  IF check_intent THEN
    prompt := prompt || E'ELSE IF [SQL2] answers [My Question] and [Manifest2] have the same underlying concept \n';
    prompt := prompt || E'   as [My Manifest], then set "intent_match" to true, produce [output] \n';
    prompt := prompt || E'   as a JSON dictionary, with \n';
    prompt := prompt || E'   the value corresponding to the key "answer" equal to [SQL2], \n';
    prompt := prompt || E'   the value corresponding to the key "manifest" equal to [Manifest2],\n';
    prompt := prompt || E'   the value corresponding to the key "intent" equal to [Intent2],\n';
    prompt := prompt || E'   the value corresponding to the key "intent_match" equal to true, and,\n';
    prompt := prompt || E'   the value corresponding to the key "dbg" equal to "template with fragments.".\n';

    prompt := prompt || E'ELSE, set the value corresponding to "intent_match" equal to false \n';
    prompt := prompt || E'   the value corresponding to "mismatch_reason" equal to the reason\n';
    prompt := prompt || E'   that [My Question] is NOT answerable by [SQL2] OR there is\n';
    prompt := prompt || E'   a concept mismatch between [My Manifest] and [Manifest2], and\n';
    prompt := prompt || E'   the value corresponding to the key "dbg" equal to "failed template with fragments".\n';
  ELSE
    prompt := prompt || E'ELSE Produce [output] as a JSON dictionary, with \n';
    prompt := prompt || E'the value corresponding to the key "answer" equal to [SQL2], \n';
    prompt := prompt || E'   the value corresponding to the key "manifest" equal to [Manifest2],\n';
    prompt := prompt || E'the value corresponding to the key "intent" equal to [Intent2], and \n';
    prompt := prompt || E'the value corresponding to the key "dbg" equal to "Template match".\n\n';
  END IF;

  prompt := prompt || E'** Step 1 **\n';
  prompt := prompt || E'a. From the [Template List], find a [Template] which has a [manifest] that \n';
  prompt := prompt || E'   has the highest SIMILARITY to [My Manifest]. [My Question] and the \n';
  prompt := prompt || E'   [question] of the chosen [Template] may not match exactly (e.g. \n';
  prompt := prompt || E'   differ in few values). The conceptual match between the manifests \n';
  prompt := prompt || E'   matters the most to me.';

  prompt := prompt || E'b. IF you could NOT find such [Template], then [SQL1] is "".\n';
  prompt := prompt || E'   ELSE, apply these rules to produce [SQL1], [Intent1], and [Manifest1]:\n';

  prompt := prompt || E'   Rule 1) The parameters in the [Parameterized SQL] of the [Template] \n';
  prompt := prompt || E'           appear as $1, $2, etc. A [Template] may not have any parameter.\n';

  prompt := prompt || E'   Rule 2) IF [Parameterized SQL] DOES NOT HAVE ANY parameter, \n';
  prompt := prompt || E'           [SQL1] is equal to the [Parameterized SQL].\n';

  prompt := prompt || E'           OTHERWISE, analyze [Question] and [Parameterized SQL] to learn \n';
  prompt := prompt || E'           the pattern to extract parameters from [My Question]. Apply the \n';
  prompt := prompt || E'           extract parameters from [My Question] to [Parameterized SQL]. \n';
  prompt := prompt || E'           More specifically, you will replace the parameters in the \n';
  prompt := prompt || E'           [Parameterized SQL] of the chosen [Template] to produce [SQL1].\n';

  prompt := prompt || E'   Rule 3) To produce [Intent1], replace the extracted parameters in \n';
  prompt := prompt || E'           [Paramertrized Intent] of the identified [Template] with the \n';
  prompt := prompt || E'           values extracted from [My Question]. Set [Manifest1] equal to the \n';
  prompt := prompt || E'           [manifest] of the identified [Template].\n';

  prompt := prompt || E'   Rule 4) When producing [SQL1], and you need to compare with strings,\n';
  prompt := prompt || E'           use single quotes around the strings, NOT double quotes.\n\n';

  prompt := prompt || E'** Step 2 **\n';
  prompt := prompt || E'a. IF there is no condition in [My Manifest] which is missing in [Manifest1], then \n';
  prompt := prompt || E'   set [SQL2] equal to [SQL1], [Intent2] equal to [Intent1], and [Manifest2] equal to [Manifest1], \n';
  prompt := prompt || E'   and you are done with [Step 2]. \n';

  prompt := prompt || E'b. ELSE, using the fragments in the [Fragment List], produce [SQL2], [Intent2], and [Manifest2] \n';
  prompt := prompt || E'   by selecting and applying predicates from the fragments in [Fragment List] to [SQL1], \n';
  prompt := prompt || E'   [Intent1], and [Manifest1]. You MUST strictly apply the following rules: \n';

  prompt := prompt || E'   Rule 5) Identify the conditions in [My Manifest] that are missing in [Manifest1]. \n';

  prompt := prompt || E'   Rule 6) Identify fragments with [Manifest] that cover a missing conditions. \n';
  prompt := prompt || E'           There might be more thant 1 fragment to covers missing conditions. \n';

  prompt := prompt || E'   Rule 7) To determine if a fragment covers a condition, analyze its [Manifest], \n';
  prompt := prompt || E'           its [Intent], and [Fragment-Predicate]. Decide if after rewriting the \n';
  prompt := prompt || E'           [Fragment-Predicate] through value replacement from [My Question], it \n';
  prompt := prompt || E'           will create a condition to cover a condition in [My Manifest] \n';
  prompt := prompt || E'           which is missing (not present) in [Manifest1].\n';

  prompt := prompt || E'   Rule 8) Apply all adjusted predicates in [Rule 7] to the WHERE clause of [SQL1],\n';
  prompt := prompt || E'           to produce [SQL2]. You must adjust the Table alias used in the predicate,\n';
  prompt := prompt || E'           with the corresponding table used in [SQL1]. If [SQL1] does not have a \n';
  prompt := prompt || E'           WHERE clause, create one.\n';

  prompt := prompt || E'   Rule 9) When producing [SQL2], and you need to compare with strings,\n';
  prompt := prompt || E'           use single quotes around the strings, NOT double quotes.\n\n';

  prompt := prompt || E'  Rule 10) For all the adjusted predicates used in [Rule 8], \n';
  prompt := prompt || E'           produce [Intent2] from [Intent1] by applying [Paramertrized Intent] \n';
  prompt := prompt || E'           with parameters replaced from value extracted from [My Question].\n';

  prompt := prompt || E'  Rule 11) Produce [Manifest2] from [Manifest1] by applying the [manifest] \n';
  prompt := prompt || E'           from the selected fragments in [Rule 7] and [Rule 8].\n';

  prompt := prompt || E'  Rule 12) The predicates that are added to [SQL1] to get [SQL2] must be combined \n';
  prompt := prompt || E'           using conjunction (AND).\n';

  prompt := prompt || E'  Rule 13) If there are redundant conditions in [SQL2], remove them from [SQL2].\n';

  prompt := prompt || E'  Rule 14) If there are redundant conditions or expressions in [Intent2], \n';
  prompt := prompt || E'           remove them from [Intent2].\n';

  prompt := prompt || E'  Rule 15) You *MUST NOT* add extra JOINS to produce [SQL2], [Intent2], and [Manifest2]. *Only* \n';
  prompt := prompt || E'           use the existing joins in [SQL1]. \n';

  prompt := prompt || E'  Rule 16) You *MUST NOT* combine the conditions (from [Fragment List]) \n';
  prompt := prompt || E'           using disjunction ("OR")\n';

  prompt := prompt || E'  Rule 17) You are *ONLY ALLOWED* to combine the predicates from the fragments \n';
  prompt := prompt || E'           in [Fragment List] using conjunction ("AND"). \n';

  prompt := prompt || E'  Rule 18) If it is not possible to produce [SQL2], e.g. no fragment \n';
  prompt := prompt || E'           in [Fragment List] to cover a missing condition, [SQL2] must be "".\n';

  prompt := prompt || E'  Rule 19) If there are contradicting conditions in [SQL2] or in [Intent2], \n';
  prompt := prompt || E'           or you need to introduce a new JOIN not in a fragment, or a predicate \n';
  prompt := prompt || E'           not inferred from a fragment in [Fragment List], set [SQL2] is equal to "".\n';

  prompt := prompt || E'  Rule 20) If it is NOT possible to produce [SQL2] by satisfying all rules, \n';
  prompt := prompt || E'           [SQL2] must be set to "".\n';
  RETURN prompt;
END;
$$ LANGUAGE plpgsql;

-- Part of the Magic machinery, to be moved into the Go library.
CREATE OR REPLACE FUNCTION alloydb_ai_nl.format_objects(
  objects JSON,
  descriptor TEXT) RETURNS TEXT
STABLE
PARALLEL SAFE
AS $$
DECLARE
  key_text TEXT;
  index INT := 1;
  value_text TEXT;
  object JSON;
  prompt TEXT := '[' || descriptor || ' List]';
BEGIN
  FOR object IN SELECT * FROM json_array_elements(objects)
  LOOP
      prompt := prompt || E'\n\n** ' || descriptor || ' ' || index || ' **';
      FOR key_text, value_text IN SELECT key, value
          FROM jsonb_each_text(object::jsonb) ORDER BY key
      LOOP
         prompt := prompt || E'\n   [' || key_text || ']: ' || value_text;
      END LOOP;
      index := index + 1;
  END LOOP;
  IF index = 1 THEN
     prompt := prompt || E'\nEmpty\n';
  END IF;
  RETURN prompt;
END;
$$ LANGUAGE plpgsql;

-- Part of the Magic machinery, to be moved into the Go library.
CREATE OR REPLACE FUNCTION alloydb_ai_nl.format_fragments(context JSON) RETURNS TEXT
STABLE
PARALLEL SAFE
AS $$
BEGIN
  IF context IS NULL OR (context ->> 'fragments') IS NULL THEN
     RETURN E'[Fragment List]\nEmpty\n';
  END IF;
  RETURN alloydb_ai_nl.format_objects(context -> 'fragments', 'Fragment');
END;
$$ LANGUAGE plpgsql;

-- Part of the Magic machinery, to be moved into the Go library.
CREATE OR REPLACE FUNCTION alloydb_ai_nl.format_templates(context JSON) RETURNS TEXT
STABLE
PARALLEL SAFE
AS $$
BEGIN
  IF context IS NULL OR (context ->> 'templates') IS NULL THEN
     RETURN E'[Template List]\nEmpty\n';
  END IF;
  RETURN alloydb_ai_nl.format_objects(context -> 'templates', 'Template');
END;
$$ LANGUAGE plpgsql;

-- Part of the Magic machinery, to be moved into the Go library.
-- Produces the prompt for Choose.
CREATE OR REPLACE FUNCTION alloydb_ai_nl.choose_prompt(
  nl_config_id TEXT, nl_question TEXT,
  nl_manifest TEXT, additional_info JSONB,
  use_empty_embedding BOOL DEFAULT FALSE) RETURNS text AS $$
DECLARE
  check_intent BOOL := (additional_info->>'method' != 'nl_choose_nointent');
  fragments JSON;
  nl_config_json JSON;
  prompt TEXT := '';
  templates JSON;
  use_fragments BOOL := (additional_info->>'method' = 'nl_choose_fragment');
BEGIN
  nl_config_json := json_build_object('nl_config_id', nl_config_id);
  templates := alloydb_ai_nl.get_templates(nl_config_json, nl_question, additional_info, nl_manifest);
  prompt := alloydb_ai_nl.format_templates(templates);
  IF use_fragments THEN
     fragments := alloydb_ai_nl.get_fragments(nl_config_json, nl_question, additional_info, nl_manifest);
     prompt := prompt || E'\n\n' || alloydb_ai_nl.format_fragments(fragments);
     prompt := alloydb_ai_nl.choose_prompt_template_fragments(check_intent) || prompt;
  ELSE
    prompt := alloydb_ai_nl.choose_prompt_template(check_intent) || prompt;
  END IF;
  prompt := REPLACE(prompt, '{nl_manifest}', nl_manifest);
  RETURN REPLACE(prompt, '{nl_question}', nl_question);
END;
$$ LANGUAGE plpgsql;

-- Part of the Magic machinery, to be moved into the Go library.
CREATE OR REPLACE FUNCTION alloydb_ai_nl.choose_build_model_input(prompt TEXT) RETURNS JSON AS $$
DECLARE
  text_to_model TEXT := '';
BEGIN
  text_to_model := jsonb_pretty(to_jsonb(prompt));
  text_to_model := substr(text_to_model, 2, length(text_to_model) - 2);
  text_to_model := '{"contents": [{"role": "user", "parts": [{"text": "' || text_to_model || '"}]}], "safety_settings": [{"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"}, {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"}, {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"}, {"category": "HARM_CATEGORY_DANGEROUS_CONTENT","threshold": "BLOCK_ONLY_HIGH"}], "generationConfig": {
          "temperature": 0,
          "topP": 1.0,
          "topK": 32,
          "candidateCount": 1,
          "maxOutputTokens": 8192
       }
     }';
  return text_to_model::json;
END;
$$ LANGUAGE plpgsql;

-- Part of the Magic machinery, to be moved into the Go library.
-- This method must not throw an exception.
CREATE OR REPLACE FUNCTION alloydb_ai_nl.choose_get_answer(
  model JSONB,
  prompt TEXT,
  check_query BOOL DEFAULT FALSE,
  retries INTEGER DEFAULT 5,
  response_schema JSONB DEFAULT NULL
) RETURNS JSON AS $$
DECLARE
  error_msg TEXT := '';
  json_data JSON;
  llm_response TEXT := '';
  parsed_response TEXT[];
  query TEXT;
  retry INTEGER := 0;
BEGIN
  WHILE retry < retries LOOP
    BEGIN
      llm_response := alloydb_ai_nl.predict(model, prompt, response_schema);
      IF response_schema IS NOT NULL THEN
        json_data := llm_response::json;
      ELSE
        parsed_response := regexp_split_to_array(llm_response, E'(\n)*```(json)?(\n)*');
        IF array_length(parsed_response, 1) > 2 THEN
          -- This line may throw, without "'" expansion.
          -- TODO (rsherkat): Avoid the following to throw without expansion.
          json_data := (REGEXP_REPLACE(parsed_response[2],'(?<!\\)''', '''''', 'g'))::json;
        END IF;
      END IF;

      EXIT WHEN json_data->>'answer' = 'I don''t know';
      IF COALESCE(json_data->>'answer', '') != '' AND check_query THEN
        --  This un-escapes any doubled-up single quotes
        -- (e.g., 'O''Malley' becomes 'O'Malley') from the extracted SQL text.
        query := REGEXP_REPLACE(json_data->>'answer', '''''', '''', 'g');
        error_msg := alloydb_ai_nl.google_is_sql_query_executable(query);
        IF error_msg != '' THEN
            -- The feedback loop here does not send back the error message (b/407519544).
            RETURN json_build_object('answer', 'I don''t know');
        END IF;
      END IF;
      EXIT WHEN error_msg = ''; -- No error
    EXCEPTION
      WHEN OTHERS THEN
        RAISE INFO E'Exception in choose_get_answer; model: %\n, prompt: %\n, llm_response:% \nError: %',
           model->>'id', prompt, llm_response, SQLERRM;
        -- TODO (rsherkat): amend the error to the prompt
    END;
    retry := retry + 1;
  END LOOP;
  RETURN CASE WHEN retry < retries THEN json_data ELSE json_build_object('answer', 'I don''t know') END;
END;
$$ LANGUAGE plpgsql;

-- Part of the Magic machinery, to be moved into the Go library.
-- Check whether the intent of a question matches with the provided parsable query.
CREATE OR REPLACE FUNCTION alloydb_ai_nl.choose_check_intent(
  nl_config_id TEXT,
  model JSONB,
  intent TEXT,
  query TEXT
) RETURNS JSON AS $$
DECLARE
  prompt TEXT := '';
BEGIN
  query := REPLACE(query, E'\\\"', '"');
  prompt := E'Your job is to output JSON dictionary:\n';
  prompt := prompt || E'        {\n';
  prompt := prompt || E'            "answer" : true\n';
  prompt := prompt || E'        }\n';
  prompt := prompt || E'if the following question:\n';
  prompt := prompt || '[Question] :' || intent;
  prompt := prompt || E'\n is answerable by the following [SQL] statement:\n';
  prompt := prompt || '[SQL]: ' || query || '\n';
  prompt := prompt || E'Else, when the [Question] is not answerable by the [SQL]\n';
  prompt := prompt || E'statement, output a JSON dictionary with two keys \n';
  prompt := prompt || E'"answer" and "reason", with the value corresponding to \n';
  prompt := prompt || E'the key "answer" is "false" and the value corresponding \n';
  prompt := prompt || E'to the key "reason" is the reason that [Question] cannot \n';
  prompt := prompt || E'be answered by [SQL]. Here is the schema of relevant tables\n';
  prompt := prompt || E'and views:\n';
  prompt := prompt || alloydb_ai_nl.google_get_accessible_schema(TRUE, '', nl_config_id);

  RETURN alloydb_ai_nl.choose_get_answer(model, prompt);
END;
$$ LANGUAGE plpgsql;

-- Part of the Magic machinery, to be moved into the Go library.
CREATE OR REPLACE FUNCTION alloydb_ai_nl.choose_check_intent_parameterized(
  nl_config_id TEXT,
  model JSONB,
  intent TEXT,
  query TEXT,
  parameterized_sql TEXT,
  nl_question TEXT
) RETURNS JSON AS $$
DECLARE
  prompt TEXT := '';
BEGIN
  query := REPLACE(query, E'\\\"', '"');
  prompt := E'I am going to provide [Question], a [SQL] statement, a [Parameterized SQL],\n';
  prompt := prompt || E'an [intent], and the [Schema] of relevant tables and views:\n';
  prompt := prompt || E'\n [Question] :' || nl_question;
  prompt := prompt || E'\n [SQL] :' || query;
  prompt := prompt || E'\n [Parameterized SQL] :' || parameterized_sql;
  prompt := prompt || E'\n [intent] :' || intent;
  prompt := prompt || E'\n [Schema] :\n';
  prompt := prompt || alloydb_ai_nl.google_get_accessible_schema(TRUE, '', nl_config_id);
  prompt := prompt || E'\n\nYour job is to output JSON dictionary, with two keys:\n';
  prompt := prompt || E'"answer" and "reason". You need to STRICTLY follow these rules:\n\n';
  prompt := prompt || E'Rule 1) IF the [SQL] statement does not answer [Question] correctly,\n';
  prompt := prompt || E'        set "answer" to "false" and set the value corresponding to \n';
  prompt := prompt || E'        the key "reason" equal to the reason that [Question] cannot \n';
  prompt := prompt || E'        be answered by [SQL].';
  prompt := prompt || E'Rule 2) ELSE IF [Parameterized SQL] is not a parametrization of [SQL]\n';
  prompt := prompt || E'        then set "answer" to "false" and set the value corresponding\n';
  prompt := prompt || E'        to the key "reason" to why parameterization is not correct.\n';
  prompt := prompt || E'Rule 3) ELSE IF [intent] does not capture the core intent of [Question],\n';
  prompt := prompt || E'        then set "answer" to "false" and set the value corresponding to \n';
  prompt := prompt || E'        the key "reason" equal to why [intent] does not match the core \n';
  prompt := prompt || E'        intent of [Question].\n';
  prompt := prompt || E'Rule 4) ELSE set "answer" to "true" and set the value corresponding to \n';
  prompt := prompt || E'        the key "reason" equal to an empty string.\n';

  RETURN alloydb_ai_nl.choose_get_answer(model, prompt);
END;
$$ LANGUAGE plpgsql;

-- Part of the Magic machinery, to be moved into the Go library.
CREATE OR REPLACE FUNCTION alloydb_ai_nl.choose_check_intent_fragment(
  nl_config_id TEXT,
  model JSONB,
  sql TEXT,
  intent TEXT,
  fragment TEXT
) RETURNS JSON AS $$
DECLARE
  prompt TEXT := '';
BEGIN
  prompt := E'I am going to provide a [SQL], an [Intent], [Fragment], and the [Schema] of relevant\n';
  prompt := prompt || E'\n tables and views.\n';
  prompt := prompt || E'\n [SQL]: ' || sql;
  prompt := prompt || E'\n [Intent]: ' || intent;
  prompt := prompt || E'\n [Fragment]: ' || fragment;
  prompt := prompt || E'\n [Schema]: \n';
  prompt := prompt || alloydb_ai_nl.google_get_accessible_schema(TRUE, '', nl_config_id);

  prompt := prompt || E'\n\nYour job is to output JSON dictionary, with two keys:\n';
  prompt := prompt || E'"answer" and "reason". You need to STRICTLY follow this rule:\n\n';
  prompt := prompt || E'Rule) IF the intent (purpose) of the [Fragment] statement matches \n';
  prompt := prompt || E'      the core intent of [Intent], in the context provided by the [SQL]\n';
  prompt := prompt || E'      statement and the comments of the objects (tables and columns)\n,';
  prompt := prompt || E'      used in the [Sql] statement and defined in the [Schema] section,\n';
  prompt := prompt || E'      then set answer" to "true" and set the value corresponding\n';
  prompt := prompt || E'      to the key "reason" equal to an empty string.\n';
  prompt := prompt || E'      ELSE set "answer" to "false" and set the value corresponding \n';
  prompt := prompt || E'      to the key "reason" equal to the reason for intent mismatch \n';
  prompt := prompt || E'      between an empty string.\n';
  RETURN alloydb_ai_nl.choose_get_answer(model, prompt);
END;
$$ LANGUAGE plpgsql;

-- Part of the Magic machinery, to be moved into the Go library.
CREATE OR REPLACE FUNCTION alloydb_ai_nl.choose_sql(
  nl_config_id TEXT,
  model JSONB,
  nl_question TEXT,
  prompt TEXT,
  retries INT DEFAULT 1,
  check_intent BOOL DEFAULT TRUE
) RETURNS JSONB AS $$
DECLARE
  intent_data JSON := '{}'::json;
  json_data JSON := '{}'::json;
  llm_calls INT := 1; -- From building manifest
  query TEXT := '';
  ret JSONB := '{}'::jsonb;
  retry INTEGER := 0;
BEGIN
  WHILE retry < retries LOOP
     -- TODO (rsherkat) When checking intent fails, we need to establish a feedback loop
     -- and provide why checking intent failed to choose_get_answer.
     json_data := alloydb_ai_nl.choose_get_answer(model, prompt, check_query => TRUE);
     llm_calls := llm_calls + 1;
     -- Undo the "'" expansion in alloydb_ai_nl.choose_get_answer.
     query := REGEXP_REPLACE(json_data->>'answer', '''''', '''', 'g');
     IF query = 'I don''t know' THEN
        RETURN jsonb_build_object(
          'toolbox_used', FALSE,
          'choose sql retries', retry,
          'LLM calls', llm_calls,
          'dbg', COALESCE(json_data->>'dbg', 'not available'));
     ELSIF check_intent THEN
        RETURN CASE WHEN lower(json_data->>'intent_match') = 'true' THEN
             jsonb_build_object('sql', query, 'intent', json_data->>'intent', 'toolbox_used', TRUE,
             'manifest', json_data->>'manifest',
             'method', 'nl_choose', 'choose sql retries', retry, 'LLM calls', llm_calls,
             'dbg', COALESCE(json_data->>'dbg', 'not available'))
        ELSE jsonb_build_object(
             'choose_sql (not picked)', query, 'toolbox_used', FALSE,
             'reason', json_data->>'mismatch_reason',
             'choose sql retries', retry, 'LLM calls', llm_calls,
             'dbg', COALESCE(json_data->>'dbg', 'not available'))
        END;
     ELSE -- No intent check!
        RETURN jsonb_build_object(
          'sql', query, 'intent', json_data->>'intent', 'toolbox_used', TRUE,
          'manifest', json_data->>'manifest',
          'method', 'nl_choose_nointent', 'choose sql retries', retry, 'LLM calls', llm_calls);
     END IF;
     retry := retry + 1;
  END LOOP;
  RETURN jsonb_build_object('choose_sql failed after retries', retry, 'LLM calls', llm_calls);
END;
$$ LANGUAGE plpgsql;

-- Part of the Magic machinery, might be decomposed and
-- moved partially to the Go library.
-- Function that may use a toolbox to synthesize the output SQL,
-- and sets ret->>toolbox_used = True when a toolbox is applied.
CREATE OR REPLACE FUNCTION alloydb_ai_nl.choose(
  nl_config_id TEXT,
  model JSONB,
  nl_question TEXT,
  additional_info JSONB,
  IN k INTEGER DEFAULT 10,
  IN param_names TEXT[] DEFAULT NULL,
  IN param_values TEXT[] DEFAULT NULL
  ) RETURNS JSON AS $$
DECLARE
  method TEXT := additional_info->>'method';
  verbose_mode BOOL := additional_info->>'verbose_mode';
  retries INT := additional_info->>'retries';
  use_value_index BOOL := additional_info->>'use_value_index';
  check_intent BOOL := (method != 'nl_choose_nointent');
  nl_manifest JSON := '{}'::json;
  prompt TEXT := '';
  ret JSONB := '{}'::jsonb;
  row_count INTEGER;
BEGIN
  -- Skip Choose when there is no Template.
  PERFORM 1 FROM alloydb_ai_nl.g_template_store LIMIT 1;
  IF NOT FOUND THEN -- No template
    RETURN jsonb_build_object('toolbox_used', FALSE, 'LLM calls', 0);
  END IF;
  SELECT COUNT(*) INTO row_count FROM alloydb_ai_nl.template_store_view
  WHERE enabled AND (config = nl_config_id);
  IF row_count = 0 THEN -- No active template for this config
    RETURN jsonb_build_object('toolbox_used', FALSE, 'LLM calls', 0);
  END IF;

  BEGIN
    nl_manifest := alloydb_ai_nl.choose_get_manifest(model, nl_question,
      use_value_index => use_value_index,
      retry_when_failure => retries,
      verbose_mode => verbose_mode,
      param_names => param_names,
      param_values => param_values);
    prompt := alloydb_ai_nl.choose_prompt(nl_config_id, nl_question,
      nl_manifest->>'manifest', additional_info);
    IF prompt != '' THEN
      ret := alloydb_ai_nl.choose_sql(nl_config_id, model, nl_question,
          prompt, 1, check_intent); -- 1 : retries
      IF verbose_mode THEN
         ret := ret || jsonb_build_object('nl_manifest', nl_manifest,
           'choose sql prompt', prompt);
      END IF;
    END IF;
  EXCEPTION
      WHEN OTHERS THEN
         RAISE NOTICE 'Error: %', SQLERRM;
         RAISE NOTICE 'Error Detail: %', SQLSTATE;
         ret := jsonb_build_object('toolbox_used', FALSE,
           'choose manifest', nl_manifest, 'choose prompt', prompt);
  END;
  RETURN ret::json;
END;
$$ LANGUAGE plpgsql;

-- Will be moved into context API.
-- Get the entity extractor template with customized concept type.
-- The customized concept type is a json list with definitions, example or counter examples.
-- Example Input:
--   {"gender": "The socially constructed roles, behaviors, expressions and identities of girls, women, boys, men, and gender diverse people.",
--    "sport": "A physical activity involving skill and exertion, often governed by a set of rules or customs and engaged in competitively."}
CREATE OR REPLACE FUNCTION alloydb_ai_nl.get_value_phrases_extractor_template(customized_concept_type JSON DEFAULT '{}') RETURNS text AS $$
BEGIN
  RETURN E'Please extract the named entity (a named entity is a real-world object, such as a person, location, organization, product, etc., that can be denoted with a proper name.) from the query literally based on the following types:\n' ||
         E'[Types]\n' ||
         E'- country\n' ||
         E'- city\n' ||
         E'- email_address\n' ||
         E'- language\n' ||
         E'- law\n' ||
         E'- organization\n' ||
         E'- person\n' ||
         E'- product\n' ||
         E'- sport or activity\n' ||
         E'- work of art\n' ||
         E'- date\n' ||
         E'- time\n' ||
         E'- number\n' ||
         E'- currency\n' ||
         E'- region\n' ||
         CASE
           WHEN (array_length(ARRAY(SELECT json_object_keys(customized_concept_type)), 1) > 0) THEN
             E'\n- ' || array_to_string(ARRAY(SELECT key || E': ' || value FROM json_each_text(customized_concept_type)), E'\n- ')
           ELSE E''
         END ||
         E'\n' ||
         E'The output of the named entities should be in a json dictionary { "named entity 1" : [type list]}\n. The [type list] associated to each value should be the list of types that the value belongs to. If the value belongs to one type, the [type list] of the value is a list with only one value. If the value belongs to two types based on the context of the question, then the [type list] should have all possible types that the value belongs to.' ||
         E'DO NOT perform any spell checking or correction. If no entities are identified, return an empty array.\n\n' ||
         E'[Query]\n{query}';
END;
$$ LANGUAGE plpgsql;

-- Given the natural language question, extract the value phrases from the question using LLM.
-- The output is a list of value phrases in text format with concept type.
-- Example input: Find the id of our customer who lives in Paris and France.
-- Example Output:
--  {"value_phrases": {"Paris": ["city", "person"], "France": ["country"]}}
CREATE OR REPLACE FUNCTION alloydb_ai_nl.value_phrases_extractor(
  model JSONB,
  nl_question TEXT,
  sql TEXT DEFAULT '',
  customized_concept_type JSON DEFAULT '{}',
  verbose_mode BOOL DEFAULT FALSE
) RETURNS JSON AS $$
DECLARE
  llm_response TEXT := '';
  parsed_response TEXT[];
  prompt TEXT;
  response_schema JSONB;
BEGIN
  prompt := alloydb_ai_nl.get_value_phrases_extractor_template(customized_concept_type);
  prompt := TRIM(REPLACE(prompt, '{query}', nl_question));
  response_schema := alloydb_ai_nl.google_get_llm_response_schema('value_phrases_extractor');
  IF sql != '' THEN
     prompt := prompt || E'The value phrases must be a literal or a constant in [Query],\n';
     prompt := prompt || E'which is also referred in the following SQL statement\n';
     prompt := prompt || E'[SQL]\n' || sql || E'\n';
  END IF;
  BEGIN
    llm_response := alloydb_ai_nl.predict(model, prompt, response_schema);

    RETURN CASE WHEN verbose_mode THEN
             (jsonb_build_object(
               'prompt', prompt,
               'llm_response', llm_response
             ) || llm_response::jsonb)::json
           ELSE
             llm_response::json
    END;
  EXCEPTION
    WHEN OTHERS THEN
      RAISE INFO E'Failed to extract value phrases: % \nError: %', nl_question, SQLERRM;
      RETURN
         CASE WHEN verbose_mode THEN jsonb_build_object(
            'prompt', prompt, 'llm_response', llm_response,
            'error', SQLERRM)::json
         ELSE '{}'::json END;
  END;
END
$$ LANGUAGE plpgsql;

-- Given a natural language statement, it extracts value phrases and creates
-- a manifest from the provided natural language statement. If a sql statement
-- is provided, each value phrase is probed against the sql statement. Only the
-- phrases that appear in the sql statement will be used to produce the manifest.
CREATE OR REPLACE FUNCTION alloydb_ai_nl.choose_get_manifest(
  model JSONB,
  nl_question TEXT,
  sql TEXT DEFAULT '',
  use_value_index BOOL DEFAULT TRUE,
  customized_concept_type JSON DEFAULT '{}',
  retry_when_failure INT DEFAULT 5,
  verbose_mode BOOL DEFAULT FALSE,
  param_names TEXT[] DEFAULT NULL,
  param_values TEXT[] DEFAULT NULL
) RETURNS JSON AS $$
DECLARE
  _type TEXT;
  _value TEXT;
  column_values jsonb;
  concept_and_values JSONB;
  idx INT;
  manifest TEXT := '';
  most_similar_concept_and_value JSONB;
  local_column TEXT;
  local_columns TEXT[];
  local_type TEXT;
  local_value TEXT;
  local_values TEXT[] DEFAULT '{}';
  phrases JSON := '{}'::json;
  phrase_key TEXT;
  type_array JSONB;
  ret_phrases JSONB := '{}'::jsonb;
  retries_left INTEGER := retry_when_failure;
  val TEXT;
BEGIN
  manifest := nl_question;
  WHILE TRUE LOOP
     BEGIN
        phrases := alloydb_ai_nl.value_phrases_extractor(
           model, nl_question, sql, customized_concept_type, verbose_mode);
        EXIT;
     EXCEPTION
        WHEN OTHERS THEN
          IF retries_left <= 0 THEN
             RAISE;
          END IF;
          retries_left := retries_left - 1;
     END;
  END LOOP;
  FOR phrase_key, type_array IN
    SELECT key, value
    FROM jsonb_each((phrases->'value_phrases')::jsonb)
    ORDER BY LENGTH(key) DESC
  LOOP
    _value := phrase_key;
    _type  := type_array ->> 0; -- TODO(pourreza): Consider making an LLM call to resolve type-array into 1 type (vs. using ->> 0).
    local_value := _value;
    local_type := _type;
    IF use_value_index THEN
      concept_and_values := alloydb_ai_nl.get_concept_and_value(ARRAY[_value]);
      most_similar_concept_and_value := alloydb_ai_nl.get_most_similar_value_and_concept_type(concept_and_values, 0);
      IF most_similar_concept_and_value IS NOT NULL AND NOT (most_similar_concept_and_value->>'is_ambiguous')::BOOL THEN
        local_values := '{}';
        local_column := most_similar_concept_and_value#>'{most_similar_concept_and_value, columns}';
        local_columns := regexp_split_to_array(local_column, E',');
        column_values = (most_similar_concept_and_value->'most_similar_concept_and_value')->'value';

        FOR idx IN 1..array_length(local_columns, 1) LOOP
          val := (column_values::jsonb ->> ('value_column' || idx::TEXT));
          local_values := array_append(local_values, val);
        END LOOP;

        local_value := (most_similar_concept_and_value#>'{most_similar_concept_and_value, value, corrected_value}')::TEXT;
        IF local_value IS NULL THEN
          FOR idx IN 1..array_length(local_values, 1) LOOP
            IF idx = 1 THEN
              local_value := alloydb_ai_nl.remove_quotes(local_values[idx]);
            ELSE
              local_value := local_values || ',' || alloydb_ai_nl.remove_quotes(local_values[idx]);
            END IF;
          END LOOP;
        END IF;

        local_type := (most_similar_concept_and_value#>'{most_similar_concept_and_value,concept_types}')::TEXT;
        local_value := alloydb_ai_nl.remove_quotes(local_value);
        local_type := alloydb_ai_nl.remove_quotes(local_type);
      END IF;
    END IF;

    IF sql IS NOT NULL AND sql <> '' THEN
       IF POSITION(_value IN sql) > 0 THEN
          manifest := REPLACE(manifest, _value, 'a given ' || local_type);
          ret_phrases := ret_phrases || jsonb_build_object(_value, jsonb_build_array(local_type));
       END IF;
    ELSE
       manifest := REPLACE(manifest, _value, 'a given ' || local_type);
    END IF;
  END LOOP;

  IF sql IS NOT NULL AND sql <> '' THEN
      RETURN CASE WHEN verbose_mode THEN
        json_build_object('value_phrases', ret_phrases::json, 'manifest', manifest,
           'get_manifest_diagnostics', phrases,
           'get_manifest_retries', retry_when_failure - retries_left) ELSE
        json_build_object('value_phrases', ret_phrases::json, 'manifest', manifest)
      END;
  END IF;

  RETURN CASE WHEN verbose_mode THEN
    json_build_object('value_phrases', phrases->'value_phrases',
       'manifest', manifest, 'get_manifest_diagnostics', phrases,
       'get_manifest_retries', retry_when_failure - retries_left) ELSE
    json_build_object('value_phrases', phrases->'value_phrases',
       'manifest', manifest) END;
END
$$ LANGUAGE plpgsql;

-- Parameterize SQL and intent.
CREATE OR REPLACE FUNCTION alloydb_ai_nl.choose_parameterize(
  value_phrases JSON, sql TEXT, intent TEXT) RETURNS JSON AS
$$
DECLARE
  _value TEXT;
  param_index INTEGER := 1;
  psql TEXT := sql;
  pintent TEXT := intent;
  search_phrase TEXT := '';
BEGIN
  FOR _value IN
    SELECT key
    FROM jsonb_object_keys(value_phrases::jsonb) AS t(key)
    ORDER BY LENGTH(key) DESC
  LOOP
    search_phrase := '''' || _value || '''';
    IF POSITION(search_phrase IN psql) > 0 AND POSITION(search_phrase IN pintent) > 0 THEN
       psql := REGEXP_REPLACE(psql, '(?<!\$)' || search_phrase, '$' || param_index, 'g');
       pintent := REGEXP_REPLACE(pintent, '(?<!\$)' || search_phrase, '$' || param_index, 'g');
    ELSIF POSITION(search_phrase IN psql) > 0 AND POSITION(_value IN pintent) > 0 THEN
       psql := REGEXP_REPLACE(psql, search_phrase, '$' || param_index, 'g');
       pintent := REGEXP_REPLACE(pintent, _value, '$' || param_index, 'g');
    ELSIF POSITION(_value IN psql) > 0 AND POSITION(search_phrase IN pintent) > 0 THEN
       psql := REGEXP_REPLACE(psql, '(?<!\$[\d]+)' || _value, '$' || param_index, 'g');
       pintent := REGEXP_REPLACE(pintent, '(?<!\$[\d]+)' || search_phrase, '$' || param_index, 'g');
    ELSIF POSITION(_value IN psql) > 0 AND POSITION(_value IN pintent) > 0 THEN
       psql := REGEXP_REPLACE(psql, '(?<!\$)' || _value, '$' || param_index, 'g');
       pintent := REGEXP_REPLACE(pintent, '(?<!\$)' || _value, '$' || param_index, 'g');
    ELSE
       CONTINUE;
    END IF;
    param_index := param_index + 1;
  END LOOP;
  RETURN json_build_object('sql', psql, 'intent', pintent);
END
$$ LANGUAGE plpgsql;

-- Add a template.
CREATE OR REPLACE FUNCTION alloydb_ai_nl.add_template(
  nl_config_id TEXT,
  intent TEXT,
  sql TEXT,
  nl_question TEXT DEFAULT '',
  sql_explanation TEXT DEFAULT '',
  comment TEXT DEFAULT '',
  weight INTEGER DEFAULT 1,
  check_intent BOOL DEFAULT FALSE
) RETURNS BOOL AS $$
DECLARE
  error_msg TEXT := '';
  manifest JSON;
  prm JSON := '{}'::json;
  model JSONB;
BEGIN
  IF sql = '' OR intent = '' THEN
    RAISE E'Both SQL and intent inputs must contain values. sql: %, intent: %', sql, intent;
  END IF;
  error_msg = alloydb_ai_nl.google_is_sql_query_executable(sql);
  IF NOT error_msg = '' THEN
    RAISE E'The sql_example is not executable.\n%\nQuery: %', error_msg, sql;
  END IF;
  PERFORM alloydb_ai_nl.g_check_alloydb_ai_nl_enabled();
  SELECT jsonb_build_object('id', model_id, 'parameters', COALESCE(model_parameters, '{}'::jsonb))
  INTO model
  FROM alloydb_ai_nl.g_magic_configuration
  WHERE configuration_id = nl_config_id;
  IF NOT FOUND THEN
    RAISE E'The configuration % does not exist.', nl_config_id;
  end if;
  nl_question := CASE WHEN nl_question IS NULL OR nl_question = '' THEN intent ELSE nl_question END;
  BEGIN
     IF check_intent THEN
       prm := alloydb_ai_nl.choose_check_intent(
          nl_config_id, model, intent, sql); -- 1 LLM call
       IF LOWER(COALESCE(prm->>'answer', '')) != 'true' THEN
          RAISE 'Checking intent failed, for nl_question:%, sql:%, reason:%',
             nl_question, sql, COALESCE(prm->>'reason', 'intent mismatch');
       END IF;
     END IF;
     manifest := alloydb_ai_nl.choose_get_manifest(
       model, nl_question, sql, use_value_index => TRUE); -- 1 LLM call
     prm := alloydb_ai_nl.choose_parameterize(
       (manifest->>'value_phrases')::json, sql, intent);
  EXCEPTION
    WHEN OTHERS THEN
      RAISE LOG E'Failed to add template, for config: %, nl_question: %, sql: %, \nError: %',
        nl_config_id, nl_question, sql, SQLERRM;
      RAISE;
  END;
  PERFORM pg_advisory_xact_lock_shared(alloydb_ai_nl.google_get_embedding_lock_key());
  INSERT INTO alloydb_ai_nl.g_template_store(
     template_context, template_nl, template_sql,
     template_intent, template_manifest, template_parameterized,
     template_embedding,
     template_comment, template_explanation, template_weight)
  VALUES (
     nl_config_id, nl_question,  sql,
     intent, manifest->>'manifest', prm,
     alloydb_ai_nl.google_embedding(manifest->>'manifest'),
     comment, sql_explanation, weight);
  RETURN TRUE;
END
$$ LANGUAGE plpgsql;

-- Add a template, by providing:
-- intent: The intent of this template
-- sql: How to answer nl_question using SQL statement (validated).
-- parameterized_sql: a parameterized SQL statement (must match sql)
-- parameterized intent: a parameterized intent (to produce intent).
-- nl_question: a natural language question (example) of this template.
-- manifest: IF not provided, nl_manifest is set to nl_question.
-- sql_explanation: Will be used during compose.
-- comment: provides extra metadata for each template.
CREATE OR REPLACE FUNCTION alloydb_ai_nl.add_template(
  nl_config_id TEXT,
  intent TEXT,
  sql TEXT,
  parameterized_sql TEXT,
  parameterized_intent TEXT,
  nl_question TEXT DEFAULT '',
  manifest TEXT DEFAULT '',
  sql_explanation TEXT DEFAULT '',
  comment TEXT DEFAULT '',
  weight INTEGER DEFAULT 1,
  check_intent BOOL DEFAULT FALSE) RETURNS BOOL AS
$$
BEGIN
RETURN alloydb_ai_nl.add_template_internal(
  nl_config_id,
  intent,
  sql,
  parameterized_sql,
  parameterized_intent,
  nl_question,
  manifest,
  sql_explanation,
  comment,
  weight,
  '{}'::json,
  check_intent);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION alloydb_ai_nl.add_template_internal(
  nl_config_id TEXT,
  intent TEXT,
  sql TEXT,
  parameterized_sql TEXT,
  parameterized_intent TEXT,
  nl_question TEXT,
  manifest TEXT,
  sql_explanation TEXT,
  comment TEXT,
  weight INTEGER,
  misc JSON,
  check_intent BOOL) RETURNS BOOL AS
$$
DECLARE
  error_msg TEXT := '';
  model JSONB;
  prm JSON := '{}'::json;
BEGIN
  IF sql = '' OR intent = '' THEN
    RAISE E'Both SQL and intent inputs must contain values. sql: %, intent: %', sql, intent;
  END IF;
  error_msg = alloydb_ai_nl.google_is_sql_query_executable(sql);
  BEGIN
    IF NOT error_msg = '' THEN
       RAISE E'The sql_example is not executable.\n%\nQuery: %', error_msg, sql;
    END IF;
    PERFORM alloydb_ai_nl.g_check_alloydb_ai_nl_enabled();
    SELECT
      jsonb_build_object(
        'id', model_id,
        'parameters', COALESCE(model_parameters, '{}'::jsonb)
      )
    INTO model
    FROM alloydb_ai_nl.g_magic_configuration
    WHERE configuration_id = nl_config_id;
    IF NOT FOUND THEN
      RAISE E'The configuration % does not exist.', nl_config_id;
    end if;
    nl_question := CASE WHEN nl_question IS NULL OR nl_question = '' THEN intent ELSE nl_question END;
    manifest := CASE WHEN manifest IS NULL OR manifest = '' THEN intent ELSE manifest END;
    IF check_intent THEN
       prm := alloydb_ai_nl.choose_check_intent_parameterized(
          nl_config_id, model, intent, sql, parameterized_sql, nl_question); -- 1 LLM call
       IF LOWER(COALESCE(prm->>'answer', '')) != 'true' THEN
          RAISE 'Checking intent failed, for nl_question:%, sql:%, reason:%',
            nl_question, sql, COALESCE(prm->>'reason', 'intent mismatch');
       END IF;
    END IF;
  EXCEPTION
    WHEN OTHERS THEN
      RAISE LOG E'Failed to add template, for config: %, nl_question: %, \nError: %',
        nl_config_id, nl_question, SQLERRM;
      RAISE;
  END;
  PERFORM pg_advisory_xact_lock_shared(alloydb_ai_nl.google_get_embedding_lock_key());
  INSERT INTO alloydb_ai_nl.g_template_store(
     template_context, template_nl, template_sql,
     template_intent, template_manifest,
     template_parameterized,
     template_embedding,
     template_comment, template_explanation, template_weight, template_misc1)
  VALUES (
     nl_config_id, nl_question,  sql,
     intent, manifest,
     json_build_object('sql', parameterized_sql, 'intent', parameterized_intent),
     alloydb_ai_nl.google_embedding(manifest),
     comment, sql_explanation, weight, misc);
  RETURN TRUE;
END
$$ LANGUAGE plpgsql;

-- Disables a template, provided the template identifier.
CREATE OR REPLACE FUNCTION alloydb_ai_nl.disable_template(id BIGINT)
RETURNS BOOLEAN AS $$
BEGIN
  PERFORM alloydb_ai_nl.g_check_alloydb_ai_nl_enabled();

  UPDATE alloydb_ai_nl.g_template_store
  SET template_active = FALSE
  WHERE template_id = id AND template_active;
  IF NOT FOUND THEN
     RETURN FALSE;
  ELSE
     RETURN TRUE;
  END IF;
END;
$$ LANGUAGE plpgsql;

-- Enables a template, provided the template identifier.
CREATE OR REPLACE FUNCTION alloydb_ai_nl.enable_template(id BIGINT)
RETURNS BOOLEAN AS $$
BEGIN
  PERFORM alloydb_ai_nl.g_check_alloydb_ai_nl_enabled();

  UPDATE alloydb_ai_nl.g_template_store
  SET template_active = TRUE
  WHERE template_id = id AND template_active = FALSE;
  IF NOT FOUND THEN
     RETURN FALSE;
  ELSE
     RETURN TRUE;
  END IF;
END;
$$ LANGUAGE plpgsql;

-- Drops a template from Template Store, provided the template's identifier.
CREATE OR REPLACE FUNCTION alloydb_ai_nl.drop_template(id BIGINT)
RETURNS BOOLEAN AS $$
DECLARE
  rows_deleted BOOLEAN := false;
BEGIN
  PERFORM alloydb_ai_nl.g_check_alloydb_ai_nl_enabled();

  EXECUTE format('DELETE FROM alloydb_ai_nl.g_template_store WHERE template_id = %L', id) || ' RETURNING TRUE'
  INTO rows_deleted;

  RETURN rows_deleted;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION alloydb_ai_nl.add_fragment(
  nl_config_id TEXT,
  table_aliases TEXT[],
  intent TEXT,
  fragment TEXT,
  comment TEXT DEFAULT '',
  weight INTEGER DEFAULT 1,
  check_intent BOOL DEFAULT TRUE
) RETURNS BOOL AS $$
DECLARE
  error_msg TEXT := '';
  manifest JSON;
  model JSONB;
  prm JSON := '{}'::json;
  sql TEXT;
BEGIN
  IF table_aliases IS NULL OR array_length(table_aliases, 1) = 0 THEN
    RAISE E'You need to provide a table alias list.';
  END IF;
  IF fragment IS NULL OR fragment = '' THEN
    RAISE E'You need to provide a valid fragment.';
  END IF;
  sql := 'SELECT 1 FROM ' || array_to_string(table_aliases, ', ') || ' WHERE ' || fragment;
  error_msg = alloydb_ai_nl.google_is_sql_query_executable(sql);
  IF error_msg != '' THEN
     sql = 'SELECT 1 FROM ' || array_to_string(table_aliases, ', ') || ' AND ' || fragment;
     error_msg = alloydb_ai_nl.google_is_sql_query_executable(sql);
  END IF;
  IF NOT error_msg = '' THEN
     RAISE E'The sql is not executable. Error: %\n, sql: %.', error_msg, sql;
  END IF;
  PERFORM alloydb_ai_nl.g_check_alloydb_ai_nl_enabled();
  SELECT
    jsonb_build_object(
      'id', model_id,
      'parameters', COALESCE(model_parameters, '{}'::jsonb)
    )
  INTO model
  FROM alloydb_ai_nl.g_magic_configuration
  WHERE configuration_id = nl_config_id;
  IF NOT FOUND THEN
    RAISE E'The configuration % does not exist.', nl_config_id;
  end if;
  BEGIN
    IF check_intent THEN
       prm := alloydb_ai_nl.choose_check_intent_fragment(
          nl_config_id, model, sql, intent, fragment); -- 1 LLM call
       IF LOWER(COALESCE(prm->>'answer', '')) != 'true' THEN
          RAISE 'Checking intent failed for fragment: %, sql: %, reason: %',
            fragment, sql, COALESCE(prm->>'reason', 'intent mismatch');
       END IF;
    END IF;
    manifest := alloydb_ai_nl.choose_get_manifest(
      model, intent, fragment); -- 1 LLM call
    prm := alloydb_ai_nl.choose_parameterize(
      (manifest->>'value_phrases')::json, fragment, intent);
  EXCEPTION
    WHEN OTHERS THEN
      RAISE LOG E'Failed to add fragment for config: %, sql: %, intent: %, fragment: %, Error: %',
         nl_config_id, sql, intent, fragment, SQLERRM;
      RAISE;
  END;
  PERFORM pg_advisory_xact_lock_shared(alloydb_ai_nl.google_get_embedding_lock_key());
  INSERT INTO alloydb_ai_nl.g_fragment_store(
     fragment_context, fragment_table_aliases,
     fragment_intent, fragment, fragment_parameterized,
     fragment_manifest, fragment_embedding,
     fragment_comment, fragment_weight)
  VALUES (
     nl_config_id, table_aliases,
     intent, fragment, prm,
     manifest->>'manifest', alloydb_ai_nl.google_embedding(manifest->>'manifest'),
     comment, weight);
  RETURN TRUE;
END
$$ LANGUAGE plpgsql;

-- add_fragment with provided manifest, and parametrization for fragment and intent.
CREATE OR REPLACE FUNCTION alloydb_ai_nl.add_fragment(
  nl_config_id TEXT,
  table_aliases TEXT[],
  intent TEXT,
  parameterized_intent TEXT,
  fragment TEXT,
  parameterized_fragment TEXT,
  manifest TEXT DEFAULT '',
  comment TEXT DEFAULT '',
  weight INTEGER DEFAULT 1,
  check_intent BOOL DEFAULT TRUE) RETURNS BOOL AS
$$
DECLARE
  error_msg TEXT := '';
  model JSONB;
  prm JSON := '{}'::json;
  sql TEXT;
BEGIN
  -- Input validation:
  IF table_aliases IS NULL OR array_length(table_aliases, 1) = 0 THEN
    RAISE E'You need to provide a table alias list.';
  END IF;
  IF fragment IS NULL OR fragment = '' THEN
    RAISE E'You need to provide a valid fragment.';
  END IF;
  sql := 'SELECT 1 FROM ' || array_to_string(table_aliases, ', ') || ' WHERE ' || fragment;
  error_msg = alloydb_ai_nl.google_is_sql_query_executable(sql);
  IF error_msg != '' THEN
     sql = 'SELECT 1 FROM ' || array_to_string(table_aliases, ', ') || ' AND ' || fragment;
     error_msg = alloydb_ai_nl.google_is_sql_query_executable(sql);
  END IF;
  IF NOT error_msg = '' THEN
     RAISE E'Error: sql is not executable. Table_aliases: %, fragment:%', table_aliases, fragment;
  END IF;
  PERFORM alloydb_ai_nl.g_check_alloydb_ai_nl_enabled();
  SELECT
      jsonb_build_object(
        'id', model_id,
        'parameters', COALESCE(model_parameters, '{}'::jsonb)
      )
    INTO model
    FROM alloydb_ai_nl.g_magic_configuration
    WHERE configuration_id = nl_config_id;
  IF NOT FOUND THEN
    RAISE E'The configuration % does not exist.', nl_config_id;
  END IF;
  BEGIN
    IF check_intent THEN
       prm := alloydb_ai_nl.choose_check_intent_fragment(
          nl_config_id, model, sql, intent, fragment); -- 1 LLM call
       IF LOWER(COALESCE(prm->>'answer', '')) != 'true' THEN
          RAISE 'Checking intent failed for fragment: %, sql: %, reason: %',
            fragment, sql, COALESCE(prm->>'reason', 'intent mismatch');
       END IF;
    END IF;
  EXCEPTION
    WHEN OTHERS THEN
      RAISE LOG E'Failed to add fragment for config: %, sql: %, intent: %, fragment: %, Error: %',
         nl_config_id, sql, intent, fragment, SQLERRM;
      RAISE;
  END;
  IF manifest = '' THEN
     manifest := intent;
  END IF;
  -- End of input verification.
  PERFORM pg_advisory_xact_lock_shared(alloydb_ai_nl.google_get_embedding_lock_key());
  INSERT INTO alloydb_ai_nl.g_fragment_store(
     fragment_context, fragment_table_aliases,
     fragment_intent, fragment, fragment_parameterized,
     fragment_manifest, fragment_embedding,
     fragment_comment, fragment_weight)
  VALUES (
     nl_config_id, table_aliases,
     intent, fragment,
     json_build_object('sql', parameterized_fragment, 'intent', parameterized_intent),
     manifest, alloydb_ai_nl.google_embedding(manifest),
     comment, weight);
  -- Returns TRUE when the fragment was added successfully.
  RETURN TRUE;
END
$$ LANGUAGE plpgsql;

-- Disables a fragment, provided the fragment identifier.
CREATE OR REPLACE FUNCTION alloydb_ai_nl.disable_fragment(id BIGINT)
RETURNS BOOLEAN AS $$
BEGIN
  PERFORM alloydb_ai_nl.g_check_alloydb_ai_nl_enabled();

  UPDATE alloydb_ai_nl.g_fragment_store
  SET fragment_active = FALSE
  WHERE fragment_id = id AND fragment_active;
  IF NOT FOUND THEN
     RETURN FALSE;
  ELSE
     RETURN TRUE;
  END IF;
END;
$$ LANGUAGE plpgsql;

-- Enables a fragment, provided the fragment identifier.
CREATE OR REPLACE FUNCTION alloydb_ai_nl.enable_fragment(id BIGINT)
RETURNS BOOLEAN AS $$
BEGIN
  PERFORM alloydb_ai_nl.g_check_alloydb_ai_nl_enabled();

  UPDATE alloydb_ai_nl.g_fragment_store
  SET fragment_active = TRUE
  WHERE fragment_id = id AND fragment_active = FALSE;
  IF NOT FOUND THEN
     RETURN FALSE;
  ELSE
     RETURN TRUE;
  END IF;
END;
$$ LANGUAGE plpgsql;

-- Drops a fragment from Fragment Store, provided the fragment's identifier.
CREATE OR REPLACE FUNCTION alloydb_ai_nl.drop_fragment(id BIGINT)
RETURNS BOOLEAN AS $$
DECLARE
  rows_deleted BOOLEAN := false;
BEGIN
  PERFORM alloydb_ai_nl.g_check_alloydb_ai_nl_enabled();

  EXECUTE format('DELETE FROM alloydb_ai_nl.g_fragment_store WHERE fragment_id = %L', id) || ' RETURNING TRUE'
  INTO rows_deleted;

  RETURN rows_deleted;
END;
$$ LANGUAGE plpgsql;