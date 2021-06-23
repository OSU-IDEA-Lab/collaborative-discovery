# Modeling Human Learning of Data Quality Rules

## Omeed's Master's thesis. Submission pending, expected June 2021.

For the server and backend setup of the system, check out the `server` branch.

For the UI and front-end implemenetation, check out the `ui` branch.

### Frontend
- Lives in `ui/`
- Implemented in React using Create React App and TypeScript
- To run, enter `yarn start` in the `ui` directory.

### Backend
- Lives in `server/`
- Implement in Python with Flask RESTful
- To run, enter the following commands in the `server` directory:
  - `pip install -r requirements.txt`
  - `python api.py`
- To run BART to inject errors, ensure Postgres 11 is running on your machine and, in `server`, run the following command:
  - `./BART/Bart_Engine/run.sh <path to XML egtask configuration file>`
- To run the post-analysis evaluation script, run the following command in `server`:
  - `python eval_h.py <real | sim> <scenario | user> <scenario # | user #>`

#### `data/`
- Datasets
- Violation configuration files
- CFD discovery module (from this paper and this repo)

#### `plots/`
- Not included in repo, but make sure the same subdirectories in the plots/ folder in this Drive live in the repo under plots/

#### `store/`
- Contains data from individual scenario runs

#### `study-utils/`
- Contains information about the users (is empty at first)

#### `api.py`
- Contains top-level logic for the server
- To run: `python api.py`

#### `build_container.sh`
- Script that builds and runs the Docker container of the backend

#### `eval_h.py`
- Post-analysis of empirical study results
- Plots and result files are output into plots/

#### `helpers.py`
- Nearly all functions that are called by api.py live in here
- Model logic, handling user feedback, and sampling tuples live here

#### `pkl2json.py`
- Convert pickle files needed for post-analysis to JSON files for easier parsing

#### `preprocessing.py`
- Prepare scenarios before having users work through them
- This should be run before having ANY users work with the system

#### `scenarios-for-study.json`
- Defines which scenarios in scenario.json will be utilized in the study

#### `scenarios-master.json`
- Base master definitions for all scenarios

#### `scenarios.json`
- Master definitions for all scenarios after preprocessing is done
- This is what the backend reads when initializing new scenarios for the user to do

#### `simulate.py`
- Run simulations of user interactions

#### `statstests.py`
- Contains various statistical test functions, e.g. Mann Kendall test

---
### Important Functions in helpers.py
#### `output_reward`
- Calculates rewards for the model for pure match, MRR, pure match w/ subset/superset, and MRR with subset/superset

#### `recordFeedback`
- Stores user labeling activity in each iteration

#### `interpretFeedback`
- Updates Beta distributions of FDs based on labeling activity (for Bayesian only)

#### `buildSample` / `returnTuples`
- Builds a new sample to show the user in the next iteration, ensuring violations of the target and alternative hypotheses are present

#### `getSupportAndVios`
- Takes an FD, dirty dataset, and clean dataset, and calculates the support (i.e. how many tuples this FD applies to) and violations of the FD in the dirty dataset

#### `fd2cfd`
- Supports getSupportAndVios
- Turns FD into a bunch of CFDs so we can parse dirty data for violations of the patterns relevant to the FD

#### `buildCompositionSpace`
- Takes output from cfddiscovery module and ensures compositions and combinations of FDs are also added to the viable hypothesis space definition
E.g. if A → B and A → C, then make sure A → BC is also in the hypothesis space

#### `initialPrior`
- Derives the initial shape parameters  and  for the Beta distribution of an FD using the supplied mean and variance values

#### `getPairs`
- Find all violation pairs for an FD in the provided dataset

#### `vioStats`
- Calculates the violations marked, violations found, and total violations with respect to an FD in the sample provided

#### `pkl2Json`
- Converts all pickle files for a given project ID (i.e. individual scenario-user run) to JSON files

#### `checkForTermination`
- Check if a terminating condition for the interaction has been met, i.e. if changes in user labeling trends are sufficiently small

#### `deriveStats`
- Calculate a wide variety of metrics and statistics that will be utilized in eval_h.py during post-analysis of empirical study results

