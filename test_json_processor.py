from schema_runner.json_workflow import MainWorkflow

# jfi = "./json_for_test.json"
# jfi = "./json_datasource.json"
jfi = "./json_with_data_section.json"
wk = MainWorkflow(jfi)
output = wk.run_all()
