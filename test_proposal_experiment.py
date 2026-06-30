# test_proposal_experiment.py
from backend.pipeline_state import set_experiment_anchor
from backend.proposal_agent import run_proposal_stage
from backend.experiment_agent import run_experiment_stage

set_experiment_anchor(
    repo_url="https://github.com/numenta/NAB",
    hypothesis="Using numenta/NAB, this study investigates anomaly detection in streaming time series data.",
    repo_id="numenta_nab",
    repo_name="numenta/NAB",
)

research_question = "How do classical and statistical anomaly detection methods compare on the NAB benchmark?"
proposal = run_proposal_stage(research_question, "")
print("\n--- PROPOSAL ---\n")
print(proposal)

experiment = run_experiment_stage(proposal)
print("\n--- EXPERIMENT ---\n")
print(experiment)