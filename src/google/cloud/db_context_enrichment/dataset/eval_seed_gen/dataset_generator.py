import asyncio
import collections
import json
import os
import warnings
from pathlib import Path
from typing import Any

from .genai_client import GenAiClient
from .generators import (
    QuestionGenerator,
    QuestionRefiner,
    QuestionReviewer,
    SQLCandidateGenerator,
)
from .schema import (
    SchemaDDL,
    SchemaProfile,
    TableProfile,
    TableSelector,
    generate_ddls_from_json_schema,
)
from .state_manager import (
    CommittedPairCollection,
    DatasetGenConfig,
    DatasetGenDbProfile,
    DatasetGenEventLogger,
    DatasetGenStates,
    PendingPairCollection,
    RejectedPairCollection,
    SqlCollection,
)

warnings.filterwarnings("ignore")


def _prepare_sql_for_execution_accuracy_check(sql: str) -> str:
    if sql.strip().endswith(";"):
        sql = sql.strip()[:-1]
    sql = sql.replace("\n", " ")
    sql = sql.strip()
    sql = f'SELECT 1 FROM ({sql}) AS validate_target LIMIT 1;'
    return sql


class SeedEvalDatasetGenerator:

    def __init__(self):
        self._genai_client = GenAiClient(timeout_secs=45)

    async def generate_sql(
        self,  task_working_dir: str) -> list[dict]:
        """Reads database schema profile and use it to generate SQL candidates.

        Args:
            task_working_dir: The directory containing the schema profile text file.

        Returns:
            SQL candidates in the format of [{"database": database_name, "golden_sql": sql, "tags": [str]}]
        """
        config = DatasetGenConfig(task_working_dir)
        dialect = config.dialect
        complexity = config.complexity
        database_name = config.database_name

        sql_candidate_generator = SQLCandidateGenerator(genai_client=self._genai_client)
        sql_collection = SqlCollection(task_working_dir)

        schema_profile = DatasetGenDbProfile(task_working_dir)
        elogger = DatasetGenEventLogger(task_working_dir)
        payload = {
            "schema_profile_path": schema_profile.path,
            "dialect": dialect,
            "complexity": complexity,
            "database_name": database_name,
            "parallelism": config.parallelism
        }

        elogger.log_event("generate_sql_triggered", payload, {})

        max_parallelism = config.parallelism
        try:
            if sql_collection.is_empty():
                candidate_sqls = await sql_candidate_generator.generate_candidates(
                    schema_profile=schema_profile.get_profile(),
                    dialect=dialect,
                    complexity=complexity,
                    count=max_parallelism
                )
                candidate_sqls = [
                    {
                        "qid": f"sql_{index}",
                        "golden_sql": sql_entry.text,
                        "database": database_name,
                        "tags": [
                            f"gen_id: {sql_entry.gen_id}",
                            f"complexity: {complexity}"
                        ]
                    }
                    for index, sql_entry in enumerate(candidate_sqls)
                ]
                sql_collection.add_sqls(candidate_sqls)
            else:
                candidate_sqls = sql_collection.get_sqls(None)

            response = {
                "sqls": [{
                    "qid": sql_entry["qid"],
                    "sql": _prepare_sql_for_execution_accuracy_check(sql_entry["golden_sql"]),
                }
                for sql_entry in candidate_sqls]
            }

            elogger.log_event("generate_sql", payload, {
                "golden_sql_sample": candidate_sqls[0] if candidate_sqls else None,
                "golden_sql_count": len(candidate_sqls),
                "golden_sqls_path": sql_collection.path,
            })
            return response
        except Exception as e:
            elogger.log_event("generate_sql_error", payload, {
                "error": str(e)
            })
            return {"sqls": []}

    async def generate_nlq(self, golden_sql_qids: str | list[dict], task_working_dir: str) -> dict[str, Any]:
        """Save the generated SQL/Question pairs to the provided generated pairs path.

        Args:
            golden_sql_qids: the qids of the golden SQL queries for which to generate questions
            task_working_dir: the directory to store the generated pairs

        Returns:
            A dictionary object which holds the results
        """

        if isinstance(golden_sql_qids, str):
            golden_sql_qids = json.loads(golden_sql_qids)
        
        if not isinstance(golden_sql_qids, list):
            raise ValueError(f"Unknown golden_sql_qids type: {type(golden_sql_qids)}")
        
        output_file_path = DatasetGenConfig(task_working_dir).output_file_path
        
        committed_pair_collection = CommittedPairCollection(output_file_path)
        pending_pair_collection = PendingPairCollection(task_working_dir)
        elogger = DatasetGenEventLogger(task_working_dir)
        schema_profile = DatasetGenDbProfile(task_working_dir)

        seen = committed_pair_collection.get_sql_set()
        sql_collection = SqlCollection(task_working_dir)
        
        golden_sqls = sql_collection.get_sqls(lambda entry: entry["qid"] in golden_sql_qids)
        rejected_sqls = sql_collection.get_sqls(lambda entry: entry["qid"] not in golden_sql_qids)
        golden_sqls = [sql_entry for sql_entry in golden_sqls if sql_entry.get("golden_sql") not in seen]

        payload = {
            "rejected_sql_sample": rejected_sqls[0] if rejected_sqls else None,
            "rejected_sql_count": len(rejected_sqls),
            "golden_sql_sample": golden_sqls[0] if golden_sqls else None,
            "golden_sql_count": len(golden_sqls),
            "schema_profile_path": schema_profile.path,
            "generated_pairs_path": pending_pair_collection.path,
        }
        elogger.log_event("generate_nlq_triggered", payload, { 
            "generated_nlq_path": pending_pair_collection.path,
            "golden_sqls_path": sql_collection.path,
        })
                
        pairs = []
        if not golden_sqls:
            status = {
                "generated_nlq_count": 0
            }
        else:
            question_generator = QuestionGenerator(genai_client=self._genai_client)

            first_sql = golden_sqls[0]
            assert "golden_sql" in first_sql, "golden_sqls must be a list of dict with 'golden_sql' key or a JSON string of such list."
            assert "database" in first_sql, "golden_sqls must be a list of dict with 'database' key or a JSON string of such list."

            mini_schema_profile = schema_profile.get_mini_profile()
            tasks = [
                question_generator.translate_sql_nl(
                    schema_profile=mini_schema_profile, 
                    sql=sql_entry["golden_sql"])
                for sql_entry in golden_sqls]
            results = await asyncio.gather(*tasks)
            elogger.log_event("generate_nlq_genai_done", payload, { 
                "generated_nlq_path": pending_pair_collection.path,
                "golden_sqls_path": sql_collection.path,
            })
            for nlq_entry, sql_entry in zip(results, golden_sqls):
                if not nlq_entry:
                    continue
                database_name = sql_entry["database"]
                tags = sql_entry.get("tags", [])
                current_question = nlq_entry.text
                pair = {
                    'database': database_name,
                    'nlq': current_question,
                    'golden_sql': sql_entry["golden_sql"],
                    "tags": tags + [
                        f"sql2nl_gen_id: {nlq_entry.gen_id}",
                    ],
                    "status": "nlq_review_pending"
                }
                pairs.append(pair)
            
            pending_pair_collection.add_pending_pairs(pairs)

            # clean up the interim golden SQLs since they are no longer needed after generating the NLQs
            sql_collection.delete()

            status = {
                "generated_nlq_count": len(pairs)
            }
        elogger.log_event("generate_nlq", payload, { 
            "generated_nlq_sample": pairs[0]["nlq"] if pairs else None,
            "generated_nlq_count": status["generated_nlq_count"], 
        })
        return status


    async def review_nlq(self, task_working_dir: str) -> dict[str, Any]:
        """Review the generated NLQs and update the tags in the generated pairs file.

        Args:
            task_working_dir: the directory to store the generated pairs

        Returns:
            A dictionary object which holds the results
        """
        output_file_path = DatasetGenConfig(task_working_dir).output_file_path

        pending_pair_collection = PendingPairCollection(task_working_dir)
        rejected_pair_collection = RejectedPairCollection(task_working_dir)
        committed_pair_collection = CommittedPairCollection(output_file_path)
        
        states = DatasetGenStates(task_working_dir)
        elogger = DatasetGenEventLogger(task_working_dir)

        states.increment_iterations()

        elogger.log_event("review_nlq_triggered", {
            "generated_pairs_path": pending_pair_collection.path,
        }, { 
            "verified_nlq_path": committed_pair_collection.path, 
            "rejected_nlq_path": rejected_pair_collection.path 
        })

        pending_pairs = pending_pair_collection.get_pairs(lambda pair: pair.get("status") == "nlq_review_pending")

        verified_pairs = []
        rejected_pairs = []
        if pending_pairs:
            reviewer = QuestionReviewer(genai_client=self._genai_client)
            tasks = [
                reviewer.review_question(
                    sql=pair["golden_sql"],
                    question=pair["nlq"])
                for pair in pending_pairs
            ]
            review_reports = await asyncio.gather(*tasks)
            rejected_pairs = []
            for report, pair in zip(review_reports, pending_pairs):
                if report:
                    if report.is_golden:
                        pair["tags"].append(f"nlq_review_report: {report.summary}")
                        pair["tags"].append(f"timestamp: {states.timestamp()}")
                        pair["tags"].append(f"elapsed_hr: {states.elapsed_time_hr()}")
                        verified_pairs.append(pair)
                    else:
                        pair["nlq_review"] = report.model_dump_json()
                        rejected_pairs.append(pair)
                else:
                    pair["status"] = "nlq_review_rejected"
                    pair["nlq_review"] = ""
                    rejected_pairs.append(pair)
        

        committed_pair_collection.add_verified_pairs(verified_pairs)
        rejected_pair_collection.add_rejected_pairs(rejected_pairs)
        
        states.update_states_on_pairs_committed(committed_pair_collection, rejected_pair_collection)
        
        # clean up the pending pairs file since all pending pairs have been processed (either verified or rejected)
        pending_pair_collection.delete()

        self._sync_resources(task_working_dir=task_working_dir)
        
        status = states.to_dict()
        elogger.log_event("review_nlq", {
            "verified_pair_sample": verified_pairs[0]["nlq"] if verified_pairs else None,
            "verified_pair_count": len(verified_pairs),
            "desired_output_pairs": states.desired_output_pairs,
            "verified_pairs_path": committed_pair_collection.path,
            "rejected_pairs_path": rejected_pair_collection.path,
        }, status)

        return status


    async def refine_nlq(self, task_working_dir: str) -> dict[str, Any]:
        """Refine the generated Question

        Args:
            task_working_dir: the directory to store the generated pairs

        Returns:
            A dictionary object which holds the results
        """
        output_file_path = DatasetGenConfig(task_working_dir).output_file_path
        committed_pair_collection = CommittedPairCollection(output_file_path)
        rejected_pair_collection = RejectedPairCollection(task_working_dir)
        elogger = DatasetGenEventLogger(task_working_dir)
        states = DatasetGenStates(task_working_dir)

        elogger.log_event("refine_nlq_triggered", {
                "rejected_pairs_sample": rejected_pair_collection.first(),
                "rejected_pairs_count": len(rejected_pair_collection),
                "verified_pairs_path": committed_pair_collection.path,
                "rejected_pairs_path": rejected_pair_collection.path,
            }, states.to_dict())
        
        if not rejected_pair_collection.is_empty():
            pending_pairs = rejected_pair_collection.pop_pairs(3)
            new_rejected_pairs = []
            new_verified_pairs = []

            refiner = QuestionRefiner(genai_client=self._genai_client)
            tasks = [
                refiner.refine_question(
                    sql=pair["golden_sql"],
                    question=pair["nlq"], 
                    question_report=pair["nlq_review"])
                for pair in pending_pairs]
            results = await asyncio.gather(*tasks)
            
            for (review_report, refined_nlq), pair in zip(results, pending_pairs):
                if review_report:
                    if review_report.is_golden:
                        pair["nlq"] = refined_nlq
                        pair["tags"].append(f"nlq_review_report: {review_report.summary}")
                        pair["tags"].append("notes: refined_nlq")
                        pair["tags"].append(f"timestamp: {states.timestamp()}")
                        pair["tags"].append(f"elapsed_hr: {states.elapsed_time_hr()}")
                        new_verified_pairs.append(pair)
                    else:
                        pair["status"] = "nlq_review_rejected"
                        pair["nlq_review"] = review_report.model_dump_json() if review_report else pair.get("nlq_review", "")
                        new_rejected_pairs.append(pair)
                else:
                    pair["status"] = "nlq_review_rejected"
                    pair["nlq_review"] = pair.get("nlq_review", "")
                    new_rejected_pairs.append(pair)
            
            committed_pair_collection.add_verified_pairs(new_verified_pairs)
            rejected_pair_collection.add_rejected_pairs(new_rejected_pairs)

            states.update_states_on_pairs_committed(committed_pair_collection, rejected_pair_collection)

            self._sync_resources(task_working_dir=task_working_dir)
            
            elogger.log_event("refine_nlq", {
                "verified_pair_sample": new_verified_pairs[0]["nlq"] if new_verified_pairs else None,
                "verified_pair_count": len(new_verified_pairs),
                "desired_output_pairs": states.desired_output_pairs,
                "committed_pairs_path": committed_pair_collection.path,
                "rejected_pairs_path": rejected_pair_collection.path
            }, states.to_dict())

        return states.to_dict()


    async def generate_database_profile(self, task_working_dir: str) -> dict[str, Any]:
        """Reads the contents from the input directory and assemble the database schema profile.
        The input directory will be removed after the database schema profile is generated and save to the output path.

        Args:
            task_working_dir: the directory to store the generated pairs

        Returns:
            None
        """
        
        input_dir = os.path.join(task_working_dir, "_dbp")
        output_path = os.path.join(task_working_dir, "db_profile.txt")

        config = DatasetGenConfig(task_working_dir)
        constraints = config.constraints

        list_schema_result_path = os.path.join(input_dir, 'tables.json')
        assert os.path.exists(list_schema_result_path), f"File not found: {list_schema_result_path}"
        list_schema_result_text = Path(list_schema_result_path).read_text(encoding='utf-8')
        schema_ddls: list[SchemaDDL] = generate_ddls_from_json_schema(list_schema_result_text)

        output_dir: str = Path(output_path).parent.as_posix()

        table_profiles = []
        table_names = []

        payload = {
            "input_dir": input_dir,
            "output_path": output_path,
            "constraints": constraints,
        }
        elogger = DatasetGenEventLogger(output_dir)

        try:
            for schema_ddl in schema_ddls:
                table_name = schema_ddl.get_table_name()
                ddl = schema_ddl.ddl
                columns = schema_ddl.columns
                full_table_name = schema_ddl.full_table_name

                table_names.append(table_name)

                sample_values_per_column = collections.defaultdict(list)
                
                column_samples_path = os.path.join(input_dir, "column_samples", f"{full_table_name}.json")
                if os.path.exists(column_samples_path):
                    column_samples = json.loads(Path(column_samples_path).read_text(encoding='utf-8'))
                    for row in column_samples:
                        column_name, column_value = row['name'], row['val']
                        sample_values_per_column[column_name].append(column_value)

                sample_rows_path = os.path.join(input_dir, "row_samples", f"{full_table_name}.json")
                sample_rows = []
                if os.path.exists(sample_rows_path):
                    sample_rows = json.loads(Path(sample_rows_path).read_text(encoding='utf-8'))

                table_profile = TableProfile(
                    table_name=table_name,
                    ddl=ddl,
                    columns=[c.name for c in columns],
                    sample_data=sample_rows,
                    sample_values_per_column=sample_values_per_column,
                )
                table_profiles.append(table_profile)

            final_context = SchemaProfile(
                table_profiles=table_profiles,
                general_context=constraints,
            ).to_string()
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(final_context, encoding='utf-8')
            response = {
                "schema_profile_path": output_path 
            }

            elogger.log_event("generate_database_profile", payload, response)

            return response
        except RuntimeError as e:
            elogger.log_event("generate_database_profile", payload, {
                "error": str(e)
            })
            return f"Error profiling database: {e}"
        

    def _sync_resources(self, task_working_dir: str) -> dict[str, Any]:
        """Reads the content from the generated pairs path and merge them to the output path.

        Args:
            task_working_dir: The directory containing the generated pairs.

        Returns:
            A dictionary object which holds the results
        """
        states = DatasetGenStates(task_working_dir)
        response = { "is_done": states.is_done(), "status": states.to_dict() }

        # remove check point files
        if states.is_done(): # clean up
            states.delete()
            RejectedPairCollection(task_working_dir).delete()
            PendingPairCollection(task_working_dir).delete()
            DatasetGenConfig(task_working_dir).delete()
            DatasetGenDbProfile(task_working_dir).delete()

        elogger = DatasetGenEventLogger(task_working_dir)
        elogger.log_event("sync_resources", { }, response)

        return response


    async def generate_database_profile_plan(self, task_working_dir: str) -> dict[str, Any]:
        """Read the full table schema and select the desired tables.

        Args:
            full_table_schema_path: The absolute path to the full table schema.
            output_dir: The absolute path to the output directory.
            output_summary_path: The absolute path to the output summary.

        Returns:
            A dictionary object which holds the results
        """
        full_table_schema_path = os.path.join(task_working_dir, "_dbp/tables.json")
        output_dir = os.path.join(task_working_dir, "_dbp")

        table_schema: list[SchemaDDL] = generate_ddls_from_json_schema(Path(full_table_schema_path).read_text(encoding='utf-8'))
        table_selector = TableSelector(genai_client=self._genai_client)
        selected_tables: list[str] = await table_selector.select_tables(tables=table_schema, top_k=8)
        
        schema_data_list = json.loads(Path(full_table_schema_path).read_text(encoding='utf-8'))
        schema_data_list = [item for item in schema_data_list if item['schema_name'] + '.' + item['object_details']['object_name'] in selected_tables]
        Path(full_table_schema_path).write_text(json.dumps(schema_data_list, indent=2), encoding='utf-8')

        table_schema = [item for item in table_schema if item.full_table_name in selected_tables]

        column_sampling_queries = []
        row_sampling_queries = []

        for table in table_schema:
            columns = table.columns
            qlist_by_cat = collections.defaultdict(list)
            qlist = []
            for column in columns:
                if column.is_primary_key or column.is_foreign_key:
                    continue
                query = f"SELECT DISTINCT {column.name} as val, '{column.name}' as name FROM {table.full_table_name} LIMIT 5"
                qlist_by_cat[column.data_type].append(query)
                qlist.append(query)
            if len(qlist) > 10:
                qlist = qlist[:10]
                for dtype in qlist_by_cat:
                    q_by_cat = qlist_by_cat[dtype][0]
                    if q_by_cat not in qlist:
                        qlist.append(q_by_cat)
            union_query = " UNION ALL ".join([f"({q})" for q in qlist])
            if union_query:
                column_sampling_queries.append({
                    'table_name': table.full_table_name,
                    'sampling_query': union_query
                })
            row_sampling_queries.append({
                'table_name': table.full_table_name,
                'sampling_query': f"SELECT * FROM {table.full_table_name} LIMIT 5"
            })

        column_sampling_query_path = os.path.join(output_dir, 'column_sampling_queries.json')
        row_sampling_query_path = os.path.join(output_dir, 'row_sampling_queries.json')
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        Path(column_sampling_query_path).write_text(json.dumps(column_sampling_queries, indent=2), encoding='utf-8')
        Path(row_sampling_query_path).write_text(json.dumps(row_sampling_queries, indent=2), encoding='utf-8')

        return {
            'plan': f'Profile the database for the following tables: {selected_tables}',
            'column_sampling_query_path': column_sampling_query_path,
            'row_sampling_query_path': row_sampling_query_path,
        }
    
    async def run_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        if 'task' not in payload:
            raise KeyError(f"'task' must be in the payload {payload}")
        task = payload.pop('task')
        if task == 'generate_sql':
            return await self.generate_sql(**payload)
        elif task == 'generate_nlq':
            return await self.generate_nlq(**payload)
        elif task == 'review_nlq':
            return await self.review_nlq(**payload)
        elif task == 'refine_nlq':
            return await self.refine_nlq(**payload)
        elif task == 'generate_database_profile':
            return await self.generate_database_profile(**payload)
        elif task == 'generate_database_profile_plan':
            return await self.generate_database_profile_plan(**payload)
        else:
            raise ValueError(f"Unknown task: '{task}' from payload {payload}")
