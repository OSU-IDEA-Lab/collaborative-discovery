import copy, random, os, json, pickle, math, itertools
from pprint import pprint
from collections import Counter
import heapq
import pandas as pd
import numpy as np
from rich.console import Console

console = Console()
BAYESIAN_SMOOTHING = 0.15    # Bayesian model hyperparameter
HP_MEMORY = 1  # Hypothesis testing model hyperparameter
HP_DECISION_THRESHOLD = 0.95  # Score threshold at which the user switches their hypothesis

# CellFeedback: An instance of feedback for a particular cell
class CellFeedback(object):
    def __init__(self, iter_num, marked, elapsed_time):
        self.iter_num = iter_num    # iteration number
        self.marked = marked            # whether or not the user marked the cell as noisy in this iteration
        self.elapsed_time = elapsed_time    # how much time has elapsed since the beginning of the interaction

    # Convert class object to a dictionary
    def asdict(self):
        return {
            'iter_num': self.iter_num,
            'marked': self.marked,
            'elapsed_time': self.elapsed_time
        }

# StudyMetric: a standardized class to represent various metrics being collected in the study
class StudyMetric(object):
    def __init__(self, iter_num, value, elapsed_time):
        self.iter_num = iter_num    # iteration number
        self.value = value  # the metric value
        self.elapsed_time = elapsed_time    # time elapsed since the beginning of the interaction

    # Convert class object to a dictionary
    def asdict(self):
        return {
            'iter_num': self.iter_num,
            'value': self.value,
            'elapsed_time': self.elapsed_time
        }

# FDMeta: An object storing all important attributes and metrics for an FD
class FDMeta(object):
    def __init__(self, fd, a, b, support, vios, vio_pairs):
        # LHS and RHS of the FD (not in set form)
        self.lhs = fd.split(' => ')[0][1:-1].split(', ')
        self.rhs = fd.split(' => ')[1].split(', ')

        # Beta distribution parameters
        self.alpha = a
        self.alpha_history = [StudyMetric(iter_num=0, value=self.alpha, elapsed_time=0)]
        self.beta = b
        self.beta_history = [StudyMetric(iter_num=0, value=self.beta, elapsed_time=0)]
        self.conf = (a / (a+b))
        self.conf_history = [StudyMetric(iter_num=0, value=self.conf, elapsed_time=0)]
        
        self.support = support  # How many tuples the FD applies to
        self.vios = vios    # Individual tuples that violate the FD
        self.vio_pairs = vio_pairs  # Pairs of tuples that together violate the FD

        # Violations found and total violations (for precision and recall)
        self.all_vios_found_history = []
        self.iter_vios_found_history = []
        self.iter_vios_total_history = []
    
    # Convert class object to dictionary
    def asdict(self):
        alpha_history = list()
        for a in self.alpha_history:
            alpha_history.append(a.asdict())

        beta_history = list()
        for b in self.beta_history:
            beta_history.append(b.asdict())
        
        conf_history = list()
        for c in self.conf_history:
            conf_history.append(c.asdict())

        return {
            'lhs': self.lhs,
            'rhs': self.rhs,
            'alpha': self.alpha,
            'alpha_history': alpha_history,
            'beta': self.beta,
            'beta_history': beta_history,
            'conf': self.conf,
            'conf_history': conf_history,
            'support': self.support,
            'vios': self.vios,
            'vio_pairs': [list(vp) for vp in self.vio_pairs]
        }

# output_reward: Takes the ground truth FD (user hypothesis), model output, and FD metadata store and calculates model rewards
def output_reward(gt, model_output, fd_metadata):
    if len(model_output) == 0:
        return 0, 0, 0, 0
    
    gt_lhs = set(gt.split(' => ')[0][1:-1].split(', '))
    gt_rhs = set(gt.split(' => ')[1].split(', '))

    try:
        n = next(i for i, x in enumerate(model_output) if x['lhs'] == gt_lhs and x['rhs'] == gt_rhs)
        pure = 1 if n == 0 else 0
        mrr = 1 / (n + 1)
    except StopIteration:
        pure, mrr = 0, 0
    
    top = model_output[0]
    if top['lhs'] == gt_lhs and top['rhs'] == gt_rhs:
        pure_sub_super = 1
    elif top['lhs'].issuperset(gt_lhs) or top['rhs'].issubset(gt_rhs):
        pure_sub_super = 1 - abs(fd_metadata[top['fd']]['f1'] - fd_metadata[gt]['f1'])
    else:
        pure_sub_super = 0
    
    try:
        top_sub_super = next((i, x) for i, x in enumerate(model_output) if (x['lhs'] == gt_lhs and x['rhs'] == gt_rhs) or (x['lhs'].issuperset(gt_lhs) or x['rhs'].issubset(gt_rhs)))
        mrr_sub_super = (1 / (top_sub_super[0] + 1)) * (1 - abs(fd_metadata[top_sub_super[1]['fd']]['f1'] - fd_metadata[gt]['f1']))
    except StopIteration:
        mrr_sub_super = 0
    
    return pure, mrr, pure_sub_super, mrr_sub_super


# Record user feedback
def recordFeedback(data, feedback, vio_pairs, project_id, current_iter, current_time):
    interaction_metadata = pickle.load( open('./store/' + project_id + '/interaction_metadata.p', 'rb') )
    # study_metrics = pickle.load( open('./store/' + project_id + '/study_metrics.p', 'rb') )
    start_time = pickle.load( open('./store/' + project_id + '/start_time.p', 'rb') )

    # Calculate elapsed time
    elapsed_time = current_time - start_time

    # Store user feedback
    for idx in data.index:
        if str(idx) in feedback.keys():
            for col in data.columns:
                interaction_metadata['feedback_history'][idx][col].append(CellFeedback(iter_num=current_iter, marked=bool(feedback[str(idx)][col]), elapsed_time=elapsed_time))
        else:
            for col in data.columns:
                interaction_metadata['feedback_history'][idx][col].append(CellFeedback(iter_num=current_iter, marked=interaction_metadata['feedback_history'][idx][col][-1].marked if current_iter > 1 else False, elapsed_time=elapsed_time))

    # Store latest sample in sample history
    interaction_metadata['sample_history'].append(StudyMetric(iter_num=current_iter, value=[int(idx) for idx in feedback.keys()], elapsed_time=elapsed_time))
    print('*** Latest feedback saved ***')

    pickle.dump( interaction_metadata, open('./store/' + project_id + '/interaction_metadata.p', 'wb') )
    print('*** Interaction metadata updates saved ***')

# Interpret user feedback and update alphas and betas for each FD in the hypothesis space
def interpretFeedback(s_in, feedback, X, sample_X, project_id, current_iter, current_time, target_fd=None):
    fd_metadata = pickle.load( open('./store/' + project_id + '/fd_metadata.p', 'rb') )
    start_time = pickle.load( open('./store/' + project_id + '/start_time.p', 'rb') )

    elapsed_time = current_time - start_time
    # Remove marked cells from consideration
    print('*** about to interpret feedback ***')
    marked_rows = list()
    for idx in feedback.index:
        for col in feedback.columns:
            if bool(feedback.at[idx, col]) is True:
                marked_rows.append(int(idx))
                break

    # Calculate P(X | \theta_h) for each FD
    for fd_m in fd_metadata.values():
        successes = 0   # number of tuples that are not in a violation of this FD in the sample
        failures = 0    # number of tuples that ARE in a violation of this FD in the sample

        # Calculate which pairs have been marked and remove them from calculation
        removed_pairs = set()
        sample_X_in_fd = {x for x in sample_X if x in fd_m.vio_pairs}
        for x, y in sample_X_in_fd:
            if x in marked_rows or y in marked_rows:
                removed_pairs.add((x, y))

        # Calculate successes and failures (to use for updating alpha and beta)
        for i in s_in.index:
            if i in marked_rows:
                continue
            if i not in fd_m.vios:  # tuple is clean
                successes += 1
            else:
                if len([x for x in removed_pairs if i in x]) > 0:   # tuple is dirty but it's part of a vio that the user caught (i.e. they marked the wrong tuple as the error but still found the vio)
                    successes += 1
                else:   # tuple is dirty and they missed the vio, or the vio isn't in a pair in the sample
                    failures += 1

        print('successes:', successes)
        print('failures:', failures)
                
        # Update alpha and beta
        fd_m.alpha += successes
        fd_m.alpha_history.append(StudyMetric(iter_num=current_iter, value=fd_m.alpha, elapsed_time=elapsed_time))
        fd_m.beta += failures
        fd_m.beta_history.append(StudyMetric(iter_num=current_iter, value=fd_m.beta, elapsed_time=elapsed_time))
        print('alpha:', fd_m.alpha)
        print('beta:', fd_m.beta)
        fd_m.conf = fd_m.alpha / (fd_m.alpha + fd_m.beta)
        fd_m.conf_history.append(StudyMetric(iter_num=current_iter, value=fd_m.conf, elapsed_time=elapsed_time))
        print('conf:', fd_m.conf)

    # Save updated alpha/beta metrics
    pickle.dump( fd_metadata, open('./store/' + project_id + '/fd_metadata.p', 'wb') )

# Build a sample
def buildSample(data, X, sample_size, project_id, current_iter, current_time, sampling_method='RANDOM'):
    # Load data
    fd_metadata = pickle.load( open('./store/' + project_id + '/fd_metadata.p', 'rb') )
    with open('./store/' + project_id + '/project_info.json', 'r') as f:
        project_info = json.load(f)
    target_fd = project_info['scenario']['target_fd']
    alt_h_list = project_info['scenario']['alt_h']
    
    # Get target FD metadata
    tfd_m = fd_metadata[target_fd]
    
    # Build alternative FD metadata dictionary
    alt_fd_m = dict()
    for h in alt_h_list:
        alt_fd_m[h] = fd_metadata[h]
    
    # Build set of alternative hypothesis violation pairs
    alt_h_vio_pairs = set()
    for h in alt_fd_m.values():
        alt_h_vio_pairs |= h.vio_pairs

    sample_X = set()
    s_out = None
    
    # Get sampling ratios for each hypothesis
    target_h_sample_ratio = project_info['scenario']['target_h_sample_ratio']
    alt_h_sample_ratio = project_info['scenario']['alt_h_sample_ratio']

    # Get the sample
    if sampling_method == 'WEIGHTED':
        s_index, sample_X = returnTuplesBasedOnFDWeights(data, sample_size, project_id)
    else:
        s_index, sample_X = returnTuples(data, tfd_m.vio_pairs, sample_size / 2, list(alt_h_vio_pairs), target_h_sample_ratio, alt_h_sample_ratio, current_iter)
    
    s_out = data.loc[s_index, :]

    print('IDs of tuples in next sample:', s_out.index)
    
    return s_out, sample_X

# Return the tuples and violations for the sample
def returnTuples(data, X, sample_size, alt_h_vio_pairs, target_h_sample_ratio, alt_h_sample_ratio, current_iter):
    s_out = set()
    
    # Add vios to the sample that violate the alt but not the target
    if len(alt_h_vio_pairs) > math.ceil(alt_h_sample_ratio * sample_size):
        alt_vios_out = random.sample(population=alt_h_vio_pairs, k=math.ceil(alt_h_sample_ratio * sample_size))
    else:
        alt_vios_out = alt_h_vio_pairs
    for (x, y) in alt_vios_out:
        s_out.add(x)
        s_out.add(y)
    
    # Add vios to the sample that violate the target but not the alt
    if len(X) > math.ceil(target_h_sample_ratio * sample_size):
        target_vios_out = random.sample(population=X, k=math.ceil(target_h_sample_ratio * sample_size))
    else:
        target_vios_out = X
    for (x, y) in target_vios_out:
        s_out.add(x)
        s_out.add(y)
    
    # Add tuples to the sample that violate neither the target nor the alt
    for i in range(0, math.ceil((1-target_h_sample_ratio-alt_h_sample_ratio)*sample_size)):
        other_tups = random.sample(population=data.index.tolist(), k=2)
        if len([x for x in alt_h_vio_pairs if other_tups[0] in x]) == 0 and len([x for x in target_vios_out if other_tups[0] in x]) == 0:
            s_out.add(other_tups[0])
        if len([x for x in alt_h_vio_pairs if other_tups[1] in x]) == 0 and len([x for x in target_vios_out if other_tups[1] in x]) == 0:
            s_out.add(other_tups[1])
    
    s_out = list(s_out)
    # Shuffle the sample
    random.shuffle(s_out)
    # sample_X = set()    # This is the set of true violation pairs in the sample
    # for i1 in s_out:
    #     for i2 in s_out:
    #         tup = (i1, i2) if i1 < i2 else (i2, i1)
    #         if tup in X:    # If i1 and i2 together form a real violation pair, add it to sample_X
    #             sample_X.add(tup)

    return list(s_out), target_vios_out

# RETURN TUPLES BASED ON WEIGHT
def returnTuplesBasedOnFDWeights(data, sample_size, project_id):

    # Get tuple and FD weights
    tuple_weights = pickle.load( open('./store/' + project_id + '/tuple_weights.p', 'rb') )
    fd_metadata = pickle.load( open('./store/' + project_id + '/fd_metadata.p', 'rb') )
    fd_weights = {k: v['conf'] for k, v in fd_metadata.items()}

    s_out = set()
    
    print('IDs of tuples in next sample:')
    while len(s_out) < sample_size:
        fd = random.choices(fd_weights.keys(), weights=fd_weights.values(), k=1).pop()  # Pick an FD to use for sampling, using weighted sampling
        fd_m = fd_metadata[fd]
        if len(fd_m['vios']) <= 1 or len(fd_m['vio_pairs']) == 0:   # If this FD has no violation pairs, pick two tuples based on tuple weights
            returned_tuples = random.choices(tuple_weights.keys(), weights=tuple_weights.values(), k=2)
            returned_tuple1, returned_tuple2 = returned_tuples[0], returned_tuples[1]
        else:   # If this FD has at least one violation pair, pick 1 pair
            returned_tuple1, returned_tuple2 = random.choice(fd_m['vio_pairs'])

        # Add the tuples to the sample if they're not already in it
        s_out.add(returned_tuple1)
        s_out.add(returned_tuple2)

        # If there are no more tuples left to pick in the dataset, stop picking tuples
        if len(s_out) >= len(tuple_weights.keys()):
            break
    
    sample_X = set()    # TODO: Build sample_X using s_out. sample_X is the set of true violation pairs in this sample
    return list(s_out), sample_X




# # # # # # # # # # # # # #
# # # # # # # # # # # # # #
# OTHER HELPER FUNCTIONS  #
# # # # # # # # # # # # # #
# # # # # # # # # # # # # #

# Get FD support and violations
def getSupportAndVios(dirty_data, clean_data, fd):
    lhs = fd.split(' => ')[0][1:-1] # lhs of the FD
    rhs = fd.split(' => ')[1]       # rhs of the FD
    clean_patterns = None
    if clean_data is not None:
        clean_patterns = fd2cfd(clean_data, lhs, rhs)   # Used to help find violations
        # Enforce one RHS to each LHS for clean patterns
        for l in clean_patterns.keys():
            if len(clean_patterns[l]) == 1:
                clean_patterns[l] = clean_patterns[l].pop()
            else:
                random_idx = random.randint(0, len(clean_patterns[l])-1)
                clean_patterns[l] = clean_patterns[l][random_idx]
    dirty_patterns = fd2cfd(dirty_data, lhs, rhs)   # Used to help find violations

    # If dirty pattern has >1 rhs, pick the clean rhs
    for l in dirty_patterns.keys():
        if len(dirty_patterns[l]) == 1:
            dirty_patterns[l] = dirty_patterns[l].pop()
        else:
            if clean_patterns is not None and l in clean_patterns.keys() and clean_patterns[l] in dirty_patterns[l]:
                dirty_patterns[l] = clean_patterns[l]
            else:
                random_idx = random.randint(0, len(dirty_patterns[l])-1)
                dirty_patterns[l] = dirty_patterns[l][random_idx]
        
    # Build support and violation list for the FD
    support = list()
    violations = list()
    for idx in dirty_data.index:
        support.append(idx) # Since it's an FD, all tuples are part of the support
        applicable_lhs = ''
        for lh in lhs.split(', '):
            applicable_lhs += lh + '=' + str(dirty_data.at[idx, lh]) + ', '
        applicable_lhs = applicable_lhs[:-2]
        applicable_rhs = dirty_patterns[applicable_lhs]
        is_vio = False
        # Check if there's a violation of the FD in this tuple
        for rhs_piece in applicable_rhs.split(', '):
            rh = rhs_piece.split('=')
            # If there's a value mismatch, it's a vio
            if str(dirty_data.at[idx, rh[0]]) != str(rh[1]):
                is_vio = True
                break
        if is_vio is True:
            violations.append(idx)
        
    return support, violations


# Convert FD to partial or full CFD
def fd2cfd(data, lhs, rhs):
    patterns = dict()
    mappings = dict()

    # Gather all the possible patterns present in the dataset for each pure FD or partial CFD
    for idx in data.index:
        lhspattern = ''
        rhspattern = ''

        # Build LHS pattern
        for clause in lhs.split(', '):
            if '=' in clause:
                lhspattern += clause + ', '
            else:
                lhspattern += clause + '=' + str(data.at[idx, clause]) + ', '
        lhspattern = lhspattern[:-2]    # Cut off trailing ', '

        # Build RHS pattern
        for clause in rhs.split(', '):
            if '=' in clause:
                rhspattern += clause + ', '
            else:
                rhspattern += clause + '=' + str(data.at[idx, clause]) + ', '
        rhspattern = rhspattern[:-2]    # Cut off trailing ', '

        # Add the tuple to the relevant LHS/RHS mapping (used to determine best pattern for the LHS)
        if lhspattern in patterns.keys():
            patterns[lhspattern].append(rhspattern)
            if (lhspattern, rhspattern) in mappings.keys():
                mappings[(lhspattern, rhspattern)].append(idx)
            else:
                mappings[(lhspattern, rhspattern)] = [idx]
        else:
            patterns[lhspattern] = [rhspattern]
            mappings[(lhspattern, rhspattern)] = [idx]

    # Pick best RHS pattern for each LHS from these candidates
    for key in patterns.keys():
        counts = Counter(patterns[key])
        get_mode = dict(counts)
        patterns[key] = [k for k, v in get_mode.items() if v == max(list(counts.values()))]

    return patterns

# Build composition space of hypotheses (i.e. FDs with RHS >1 tuple)
def buildCompositionSpace(fds, h_space, dirty_data, clean_data, min_conf, max_ant):
    composed_fds = set(fds)
    composed_combos = set()
    for fd1 in fds:
        for fd2 in fds:
            if fd1 == fd2 or (fd1, fd2) in composed_combos or (fd2, fd1) in composed_combos:
                continue
            fd1_lhs = set(fd1.split(' => ')[0][1:-1].split(', '))
            fd1_rhs = set(fd1.split(' => ')[1].split(', '))
            fd2_lhs = set(fd2.split(' => ')[0][1:-1].split(', '))
            fd2_rhs = set(fd2.split(' => ')[1].split(', '))

            # Skip this FD combination if there is overlap between LHS and RHS between the two
            if not fd1_rhs.isdisjoint(fd2_lhs) or not fd2_rhs.isdisjoint(fd1_lhs):
                continue

            # Skip this FD combination if the combined LHS is too complex
            composed_fd_lhs_set = fd1_lhs | fd2_lhs
            if len(composed_fd_lhs_set) > max_ant:
                continue
            
            composed_fd_lhs = '(' + ', '.join(composed_fd_lhs_set) + ')'

            if h_space is not None: # H space already exists, so match the LHS with a currently existing FD if possible
                try:
                    matching_fd = next(h['cfd'] for h in h_space if composed_fd_lhs_set == set(h['cfd'].split(' => ')[0][1:-1].split(', ')))
                    matching_fd_lhs = matching_fd.split(' => ')[0]  # Ensures the LHS is in an order that does not throw off future calculations
                    composed_fd_lhs = matching_fd_lhs
                except StopIteration:
                    pass

            composed_fd_rhs_set = fd1_rhs | fd2_rhs
            composed_fd_rhs = ', '.join(composed_fd_rhs_set)

            if h_space is not None: # H space already exists, so match the RHS with a currently existing FD if possible
                try:
                    matching_fd = next(h['cfd'] for h in h_space if composed_fd_lhs_set == set(h['cfd'].split(' => ')[0][1:-1].split(', ')) and composed_fd_rhs_set == set(h['cfd'].split(' => ')[1].split(', ')))
                    matching_fd_rhs = matching_fd.split(' => ')[1]    # Ensures the RHS is in an order that does not throw off future calculations
                    composed_fd_rhs = matching_fd_rhs
                except StopIteration:
                    pass

            composed_fd = composed_fd_lhs + ' => ' + composed_fd_rhs
            
            try:    # Prune duplicates from space of composed FDs
                _ = next(h for h in composed_fds if composed_fd_lhs_set == set(h.split(' => ')[0][1:-1].split(', ')) and composed_fd_rhs_set == set(h.split(' => ')[1].split(', ')))
                pass
            except StopIteration:
                composed_fds.add(composed_fd)

            composed_combos.add((fd1, fd2))

    # Go one level further
    further_composed_fds = set(composed_fds)
    for fd1 in composed_fds:
        for fd2 in composed_fds:
            if fd1 == fd2 or (fd1, fd2) in composed_combos or (fd2, fd1) in composed_combos:
                continue
            fd1_lhs = set(fd1.split(' => ')[0][1:-1].split(', '))
            fd1_rhs = set(fd1.split(' => ')[1].split(', '))
            fd2_lhs = set(fd2.split(' => ')[0][1:-1].split(', '))
            fd2_rhs = set(fd2.split(' => ')[1].split(', '))

            # Skip this FD combination if there is overlap between LHS and RHS between the two
            if not fd1_rhs.isdisjoint(fd2_lhs) or not fd2_rhs.isdisjoint(fd1_lhs):
                continue

            # Skip this FD combination if the combined LHS is too complex
            composed_fd_lhs_set = fd1_lhs | fd2_lhs
            if len(composed_fd_lhs_set) > max_ant:
                continue
            
            composed_fd_lhs = '(' + ', '.join(composed_fd_lhs_set) + ')'

            if h_space is not None: # H space already exists, so match the LHS with a currently existing FD if possible
                try:
                    matching_fd = next(h['cfd'] for h in h_space if composed_fd_lhs_set == set(h['cfd'].split(' => ')[0][1:-1].split(', ')))
                    matching_fd_lhs = matching_fd.split(' => ')[0]  # Ensures the LHS is in an order that does not throw off future calculations
                    composed_fd_lhs = matching_fd_lhs
                except StopIteration:
                    pass

            composed_fd_rhs_set = fd1_rhs | fd2_rhs
            composed_fd_rhs = ', '.join(composed_fd_rhs_set)

            if h_space is not None: # H space already exists, so match the RHS with a currently existing FD if possible
                try:
                    matching_fd = next(h['cfd'] for h in h_space if composed_fd_lhs_set == set(h['cfd'].split(' => ')[0][1:-1].split(', ')) and composed_fd_rhs_set == set(h['cfd'].split(' => ')[1].split(', ')))
                    matching_fd_rhs = matching_fd.split(' => ')[1]    # Ensures the RHS is in an order that does not throw off future calculations
                    composed_fd_rhs = matching_fd_rhs
                except StopIteration:
                    pass

            composed_fd = composed_fd_lhs + ' => ' + composed_fd_rhs
            
            try:    # Prune duplicates from space of composed FDs
                _ = next(h for h in further_composed_fds if composed_fd_lhs_set == set(h.split(' => ')[0][1:-1].split(', ')) and composed_fd_rhs_set == set(h.split(' => ')[1].split(', ')))
                pass
            except StopIteration:
                further_composed_fds.add(composed_fd)

            composed_combos.add((fd1, fd2))

    composition_space = [{ 'cfd': h['cfd'] } for h in h_space] if h_space is not None else list()
    for composed_fd in further_composed_fds:
        if clean_data is not None:
            support, vios = getSupportAndVios(dirty_data, clean_data, composed_fd)
            conf = (len(support) - len(vios)) / len(support)
            if conf >= min_conf and len(composed_fd.split(' => ')[0][1:-1].split(', ')) <= max_ant:
                composition_space.append({
                    'cfd': composed_fd
                })
        else:
            if len(composed_fd.split(' => ')[0][1:-1].split(', ')) <= max_ant:
                composition_space.append({
                    'cfd': composed_fd
                })

    return composition_space

# Calculate the initial prior (alpha/beta) for an FD
def initialPrior(mu, variance):
    if mu == 1:
        mu = 0.9999
    elif mu == 0:
        mu = 0.0001
    beta = (1 - mu) * ((mu * (1 - mu) / variance) - 1)
    alpha = (mu * beta) / (1 - mu)
    return abs(alpha), abs(beta)

# Get violation pairs for an FD
def getPairs(data, support, fd):
    vio_pairs = set()
    lhs = fd.split(' => ')[0][1:-1].split(', ')
    rhs = fd.split(' => ')[1].split(', ')
    for idx1 in support:
        for idx2 in support:
            if idx1 == idx2:
                continue
            
            # Initialize a representation of the pair
            pair = (idx1, idx2) if idx2 > idx1 else (idx2, idx1)
            match = True

            # Check if these tuples have matching LHS values
            for lh in lhs:
                if data.at[idx1, lh] != data.at[idx2, lh]:
                    match = False
                    break
            
            # If it is a matching pair, check if any RHS values conflict with each other
            if match is True:
                for rh in rhs:
                    if data.at[idx1, rh] != data.at[idx2, rh]:
                        vio_pairs.add(pair) # This is a violation pair; add it to the set
                        break

    return list(vio_pairs)   

# Derive total violations for the FD, violations found, and violations marked
# NOTE: t_sample is the full sample accounting for short, medium, or long-term memory, while curr_sample is only the current sample
def vioStats(curr_sample, t_sample, feedback, vio_pairs, attrs, dirty_dataset, clean_dataset):
    vios_marked = set()
    vios_total = set()
    vios_found = set()

    for x, y in vio_pairs:
        if x not in t_sample or y not in t_sample:  # If either of x or y are not in the full sample we're evaluating, skip this pair
            continue
        if x not in curr_sample and y not in curr_sample:   # If both x and y are not in the current sample, skip this pair
            continue
        vios_total.add((x, y))

        # Check if the user marked the violation
        x_marked = False
        for attr in attrs:
            if feedback[str(x)][attr] is True:  # This user marekd at least one attribute in x
                x_marked = True
                break
        y_marked = False
        for attr in attrs:
            if feedback[str(y)][attr] is True:  # The user marked at least one attribute in y
                y_marked = True
                break
        if x_marked == y_marked and x_marked is False:  # The user marked nothing; they didn't find this violation; skip
            continue

        vios_marked.add((x,y))
        vios_found.add((x,y))
    
    # Look through all non-violating tuples to see if the user marked anything incorrectly
    for x in curr_sample:
        vios_w_x = {i for i in vios_marked if x in i}   # Make sure no violation pairs have x
        if len(vios_w_x) == 0:
            marked = False
            for attr in attrs:
                if feedback[str(x)][attr] is True:  # The user marked this tuple
                    marked = True
                    break
            if marked is True:
                vios_marked.add((x,x))

    return vios_marked, vios_found, vios_total

# Convert pickle files in ./store/ to JSON (for post-analysis in eval_h.py and other scripts)
def pkl2Json(project_id):
    files = os.listdir('./store/' + project_id + '/')
    for f in files:
        print('./store/' + project_id + '/' + f)
        if '.p' in f:
            obj = pickle.load( open('./store/' + project_id + '/' + f, 'rb') )
            if type(obj) == dict:
                if f == 'fd_metadata.p':
                    for k in obj.keys():
                        obj[k] = obj[k].asdict()
                elif f == 'interaction_metadata.p':
                    for idx in obj['feedback_history'].keys():
                        for col in obj['feedback_history'][idx].keys():
                            obj['feedback_history'][idx][col] = [i.asdict() for i in obj['feedback_history'][idx][col]]
                    obj['user_hypothesis_history'] = [i.asdict() for i in obj['user_hypothesis_history']]
                    obj['sample_history'] = [i.asdict() for i in obj['sample_history']]
                elif f == 'study_metrics.p':
                    for idx in obj.keys():
                        obj[idx] = [i.asdict() for i in obj[idx]]

                with open('./store/' + project_id + '/' + f.split('.')[0] + '.json', 'w') as fp:
                    json.dump(obj, fp, ensure_ascii=False, indent=4)

# Check if a terminating condition is met for this run
def checkForTermination(project_id):
    pkl2Json(project_id)
    with open('./store/' + project_id + '/study_metrics.json', 'r') as f:
        study_metrics = json.load(f)
    with open('./store/' + project_id + '/fd_metadata.json', 'r') as f:
        fd_metadata = json.load(f)
    with open('./store/' + project_id + '/project_info.json', 'r') as f:
        project_info = json.load(f)
    with open('./store/' + project_id + '/interaction_metadata.json', 'r') as f:
        interaction_metadata = json.load(f)
    dirty_dataset = pd.read_csv(project_info['scenario']['dirty_dataset'], keep_default_na=False)
    clean_dataset = pd.read_csv(project_info['scenario']['clean_dataset'], keep_default_na=False)
    target_fd = project_info['scenario']['target_fd']

    h_space = project_info['scenario']['hypothesis_space']
    clean_h_space = project_info['scenario']['clean_hypothesis_space']
    study_metrics, fd_metadata = deriveStats(   # Gather stats
        interaction_metadata,
        fd_metadata,
        h_space,
        study_metrics,
        dirty_dataset,
        clean_dataset,
        target_fd
    )

    with open('./store/' + project_id + '/study_metrics.json', 'w') as f:
        json.dump(study_metrics, f, indent=4)
    with open('./store/' + project_id + '/fd_metadata.json', 'w') as f:
        json.dump(fd_metadata, f, indent=4)

    if (len(study_metrics['st_vios_marked'][-1]['value']) == 0):
        return False
    
    # If precision and recall has been fairly stable over the last few iterations, terminate
    st_vio_precision = [i['value'] for i in study_metrics['st_vio_precision']]
    st_vio_recall = [i['value'] for i in study_metrics['st_vio_recall']]
    if (st_vio_precision[-1] >= 0.8 and abs(st_vio_precision[-1] - st_vio_precision[-2]) <= 0.1 and abs(st_vio_precision[-2] - st_vio_precision[-3]) <= 0.1):
        if (st_vio_recall[-1] >= 0.6 and (abs(st_vio_recall[-1] - st_vio_recall[-2]) <= 0.1 and abs(st_vio_precision[-2] - st_vio_precision[-3]) <= 0.1)):
            return True
        elif (st_vio_recall[-1] >= 0.5 and (abs(st_vio_recall[-1] - st_vio_recall[-2]) <= 0.05 and abs(st_vio_precision[-2] - st_vio_precision[-3]) <= 0.05)):
            return True
        else:
            return False
    else:
        return False

# Derive post-analysis stats and metrics
def deriveStats(interaction_metadata, fd_metadata, h_space, study_metrics, dirty_dataset, clean_dataset, target_fd, max_iters=None):
    feedback_history = interaction_metadata['feedback_history'] # User feedback history throughout interaction
    user_hypothesis_history = interaction_metadata['user_hypothesis_history']   # The user's submitted hypothesis history

    # st = short-term, lt = long-term, mt = mid-term (current + last sample), mt-2 = current + last 2 samples, mt-3 = current + last 3 samples
    study_metrics['st_vio_precision'] = list()  # Short-term user precision (current sample only)
    study_metrics['lt_vio_precision'] = list()  # Long-term user precision
    study_metrics['mt_vio_precision'] = list()  # Mid-term (current + last sample) precision
    study_metrics['mt_2_vio_precision'] = list()    # Mid-term (current + last 2) precision
    study_metrics['mt_3_vio_precision'] = list()    # Mid-term (current + last 3) precision
    study_metrics['st_vio_recall'] = list() # User recall
    study_metrics['lt_vio_recall'] = list()
    study_metrics['mt_vio_recall'] = list()
    study_metrics['mt_2_vio_recall'] = list()
    study_metrics['mt_3_vio_recall'] = list()
    study_metrics['st_vio_f1'] = list() # User f1-score
    study_metrics['lt_vio_f1'] = list()
    study_metrics['mt_vio_f1'] = list()
    study_metrics['mt_2_vio_f1'] = list()
    study_metrics['mt_3_vio_f1'] = list()

    # Vios marked by the user
    study_metrics['st_vios_marked'] = list()
    study_metrics['mt_vios_marked'] = list()
    study_metrics['mt_2_vios_marked'] = list()
    study_metrics['mt_3_vios_marked'] = list()
    study_metrics['lt_vios_marked'] = list()

    # True vios found by the user
    study_metrics['st_vios_found'] = list()
    study_metrics['mt_vios_found'] = list()
    study_metrics['mt_2_vios_found'] = list()
    study_metrics['mt_3_vios_found'] = list()
    study_metrics['lt_vios_found'] = list()

    # All true vios shown to the user
    study_metrics['st_vios_total'] = list()
    study_metrics['mt_vios_total'] = list()
    study_metrics['mt_2_vios_total'] = list()
    study_metrics['mt_3_vios_total'] = list()
    study_metrics['lt_vios_total'] = list()

    # Cumulative user recall, precision, and f1-score (noover = no overlap, i.e. count each violation only once. If it occurs between samples only consider the latest occurrence)
    study_metrics['cumulative_recall'] = list()
    study_metrics['cumulative_recall_noover'] = list()
    study_metrics['cumulative_precision'] = list()
    study_metrics['cumulative_precision_noover'] = list()
    study_metrics['cumulative_f1'] = list()
    study_metrics['cumulative_f1_noover'] = list()

    # Bayesian and hypothesis testing predictions
    study_metrics['bayesian_prediction'] = [{ 'iter_num': user_hypothesis_history[0]['iter_num'], 'value': user_hypothesis_history[0]['value'][0], 'elapsed_time': user_hypothesis_history[0]['elapsed_time'] }]
    study_metrics['hp_prediction'] = [{ 'iter_num': user_hypothesis_history[0]['iter_num'], 'value': user_hypothesis_history[0]['value'][0], 'elapsed_time': user_hypothesis_history[0]['elapsed_time'] }]
    
    # top-1 output
    study_metrics['bayesian_match_1'] = list()  # top-1 perfect match boolean
    study_metrics['hp_match_1'] = list()
    study_metrics['bayesian_match_mrr_1'] = list()  # top-1 perfect match MRR
    study_metrics['hp_match_mrr_1'] = list()
    study_metrics['bayesian_match_penalty_1'] = list()  # top-1 perfect match boolean w/ subset/superset considerations
    study_metrics['hp_match_penalty_1'] = list()
    study_metrics['bayesian_match_mrr_penalty_1'] = list()  # top-1 perfect match MRR w/ subset/superset considerations
    study_metrics['hp_match_mrr_penalty_1'] = list()

    # top-3 output
    study_metrics['bayesian_match_3'] = list()
    study_metrics['hp_match_3'] = list()
    study_metrics['bayesian_match_mrr_3'] = list()
    study_metrics['hp_match_mrr_3'] = list()
    study_metrics['bayesian_match_penalty_3'] = list()
    study_metrics['hp_match_penalty_3'] = list()
    study_metrics['bayesian_match_mrr_penalty_3'] = list()
    study_metrics['hp_match_mrr_penalty_3'] = list()

    # top-5 output
    study_metrics['bayesian_match_5'] = list()
    study_metrics['hp_match_5'] = list()
    study_metrics['bayesian_match_mrr_5'] = list()
    study_metrics['hp_match_mrr_5'] = list()
    study_metrics['bayesian_match_penalty_5'] = list()
    study_metrics['hp_match_penalty_5'] = list()
    study_metrics['bayesian_match_mrr_penalty_5'] = list()
    study_metrics['hp_match_mrr_penalty_5'] = list()

    # In first iteration, the best hypothesis is the user's initial prior
    max_h = user_hypothesis_history[0]['value'][0]
    num_not_sub_super = len([h for h in h_space if max_h != 'Not Sure' and (\
        not set(h['cfd'].split(' => ')[0][1:-1].split(', ')).issuperset(set(max_h.split(' => ')[0][1:-1].split(', '))) and \
        not set(h['cfd'].split(' => ')[1].split(', ')).issubset(set(max_h.split(' => ')[1].split(', '))))])
    console.log(num_not_sub_super)

    # Make sure the user's hypothesis maps in form to one of the FDs in the hypothesis space
    for h in h_space:
        lhs = set(h['cfd'].split(' => ')[0][1:-1].split(', '))
        rhs = set(h['cfd'].split(' => ')[1].split(', '))
        try:
            existing_fds = list(fd_metadata.keys())
            existing_fd = next(ef for ef in existing_fds if set(ef.split(' => ')[0][1:-1].split(', ')) == lhs and set(ef.split(' => ')[1].split(', ')) == rhs)
            fd = existing_fd
        except StopIteration as e:
            fd = h['cfd']

        if max_h != 'Not Sure':
            lhs = set(fd.split(' => ')[0][1:-1].split(', '))
            rhs = set(fd.split(' => ')[1].split(', '))

            max_h_lhs = set(max_h.split(' => ')[0][1:-1].split(', '))
            max_h_rhs = set(max_h.split(' => ')[1].split(', '))
            if max_h_lhs == lhs and max_h_rhs == rhs:
                max_h = fd
            else:
                try:
                    existing_fds = list(fd_metadata.keys())
                    existing_fd = next(ef for ef in existing_fds if set(ef.split(' => ')[0][1:-1].split(', ')) == max_h_lhs and set(ef.split(' => ')[1].split(', ')) == max_h_rhs)
                    max_h = existing_fd
                except StopIteration as e:
                    console.log(e)
                    return

        # Derive initial alpha and beta of the FD's Beta distribution
        variance = 0.0025
        if max_h == 'Not Sure':
            alpha = 1
            beta = 1
            mu = 1 / len(h_space)
        elif fd == max_h:
            mu = 1 - BAYESIAN_SMOOTHING
            alpha, beta = initialPrior(mu, variance)
        elif lhs.issuperset(max_h_lhs) or rhs.issubset(max_h_rhs):
            mu = (1 - BAYESIAN_SMOOTHING) * (1 - abs(fd_metadata[fd]['f1'] - fd_metadata[max_h]['f1']))
            alpha, beta = initialPrior(mu, variance)
        else:
            mu = 0 if num_not_sub_super == 0 else BAYESIAN_SMOOTHING / num_not_sub_super
            alpha, beta = initialPrior(mu, variance)
        
        fd_metadata[fd]['alpha'] = alpha
        fd_metadata[fd]['beta'] = beta
        fd_metadata[fd]['conf'] = mu

        fd_metadata[fd]['alpha_history'] = [{ 'iter_num': 0, 'value': alpha, 'elapsed_time': 0 }]
        fd_metadata[fd]['beta_history'] = [{ 'iter_num': 0, 'value': beta, 'elapsed_time': 0 }]
        fd_metadata[fd]['precision_history'] = list()
        fd_metadata[fd]['recall_history'] = list()
        fd_metadata[fd]['f1_history'] = list()
        fd_metadata[fd]['vios_in_sample'] = list()
    
    all_mu_sum = sum([f['conf'] for f in fd_metadata.values()])
    for f in fd_metadata.values():
        f['conf'] /= all_mu_sum
        fd_metadata[fd]['conf_history'] = [{ 'iter_num': 0, 'value': f['conf'], 'elapsed_time': 0 }]

    if max_iters is not None:
        iters = range(1, min(max_iters, len(interaction_metadata['sample_history']))+1)
    else:
        iters = range(1, len(interaction_metadata['sample_history'])+1)
    for i in iters:

        # Calculate metrics about user labeling accuracy
        st_vios_found = set()
        st_vios_total = set()
        st_vios_marked = set()
        mt_vios_found = set()
        mt_vios_total = set()
        mt_vios_marked = set()
        mt_2_vios_found = set()
        mt_2_vios_total = set()
        mt_2_vios_marked = set()
        mt_3_vios_found = set()
        mt_3_vios_total = set()
        mt_3_vios_marked = set()
        lt_vios_found = set()
        lt_vios_total = set()
        lt_vios_marked = set()

        curr_sample = interaction_metadata['sample_history'][i-1]['value']
        mt_sample = set(curr_sample)
        mt_2_sample = set(curr_sample)
        mt_3_sample = set(curr_sample)
        if i > 1:
            mt_sample |= set(interaction_metadata['sample_history'][i-2]['value'])
            mt_2_sample |= set(interaction_metadata['sample_history'][i-2]['value'])
            mt_3_sample |= set(interaction_metadata['sample_history'][i-2]['value'])
            if i > 2:
                mt_2_sample |= set(interaction_metadata['sample_history'][i-3]['value'])
                mt_3_sample |= set(interaction_metadata['sample_history'][i-3]['value'])
                if i > 3:
                    mt_3_sample |= set(interaction_metadata['sample_history'][i-4]['value'])
        lt_sample = set(curr_sample)
        for ix in range(2, i+1):
            lt_sample |= set(interaction_metadata['sample_history'][i-ix]['value'])
        elapsed_time = interaction_metadata['sample_history'][i-1]['elapsed_time']

        feedback = dict()
        marked_rows = set()
        for x in feedback_history.keys():
            feedback[x] = dict()
            for y in feedback_history[x].keys():
                feedback[x][y] = feedback_history[x][y][i-1]['marked']
                if feedback[x][y] is True and x not in marked_rows:
                    marked_rows.add(x)

        marked_rows = [int(r) for r in marked_rows]
        
        target_sample_X_in_fd = {(x, y) for (x, y) in fd_metadata[target_fd]['vio_pairs'] if x in curr_sample and y in curr_sample}
        fd_metadata[target_fd]['vios_in_sample'].append({ 'iter_num': i, 'value': list(target_sample_X_in_fd), 'elapsed_time': elapsed_time })
        all_target_relevant_vio_pairs = set()

        oldest_iter = 0 if i < HP_MEMORY + 1 else (i - HP_MEMORY) - 1
        for it in range(oldest_iter, i):
            all_target_relevant_vio_pairs |= set(fd_metadata[target_fd]['vios_in_sample'][it]['value'])

        # Update each FD's Beta distribution
        for h in h_space:
            fd = h['cfd']
            lhs = set(fd.split(' => ')[0][1:-1].split(', '))
            rhs = set(fd.split(' => ')[1].split(', '))
            try:
                existing_fds = list(fd_metadata.keys())
                existing_fd = next(ef for ef in existing_fds if set(ef.split(' => ')[0][1:-1].split(', ')) == lhs and set(ef.split(' => ')[1].split(', ')) == rhs)
                fd = existing_fd
            except StopIteration:
                continue

            successes = 0
            failures = 0
            fd_m = fd_metadata[fd]

            removed_pairs = set()
            sample_X_in_fd = {(x, y) for (x, y) in fd_m['vio_pairs'] if x in curr_sample and y in curr_sample}
            for x, y in sample_X_in_fd:
                if int(x) in marked_rows or int(y) in marked_rows:
                    removed_pairs.add((int(x), int(y)))
            
            if fd != target_fd:
                fd_m['vios_in_sample'].append({ 'iter_num': i, 'value': list(sample_X_in_fd), 'elapsed_time': elapsed_time })
            
            # for ix in curr_sample:
            #     if str(ix) in marked_rows:
            #         continue
            #     if len([x for x in sample_X_in_fd if ix in x and x not in removed_pairs]) == 0:
            #         successes += 1  # S
            #     else:
            #         failures += 1

            # Calculate successes and failures (to use for updating alpha and beta)
            for ix in curr_sample:
                if ix in marked_rows:
                    continue
                if ix not in fd_m['vios']:  # tuple is clean
                    successes += 1
                else:
                    if len([x for x in removed_pairs if ix in x]) > 0:   # tuple is dirty but it's part of a vio that the user caught (i.e. they marked the wrong tuple as the error but still found the vio)
                        successes += 1
                    else:   # tuple is dirty and they missed the vio, or the vio isn't in a pair in the sample
                        failures += 1

            fd_m['alpha'] += successes
            fd_m['beta'] += failures
            fd_m['conf'] = fd_m['alpha'] / (fd_m['alpha'] + fd_m['beta'])
            
            fd_m['alpha_history'].append({ 'iter_num': i, 'value': fd_m['alpha'], 'elapsed_time': elapsed_time })
            fd_m['beta_history'].append({ 'iter_num': i, 'value': fd_m['beta'], 'elapsed_time': elapsed_time })
            fd_m['conf_history'].append({ 'iter_num': i, 'value': fd_m['conf'], 'elapsed_time': elapsed_time })

            # Calculate this FD's precision, recall, and f1-score over the observed data
            all_relevant_vio_pairs = set()
            for it in range(oldest_iter, i):
                all_relevant_vio_pairs |= set(fd_m['vios_in_sample'][it]['value'])

            fd_precision = 0 if len(all_relevant_vio_pairs) == 0 else len({i for i in all_relevant_vio_pairs if i in all_target_relevant_vio_pairs}) / len(all_relevant_vio_pairs)
            fd_recall = len({i for i in all_relevant_vio_pairs if i in all_target_relevant_vio_pairs}) / len(all_target_relevant_vio_pairs)
            fd_f1 = 0 if fd_precision == 0 and fd_recall == 0 else ((2 * fd_precision * fd_recall) / (fd_precision + fd_recall))

            fd_m['precision_history'].append({ 'iter_num': i, 'value': fd_precision, 'elapsed_time': elapsed_time })
            fd_m['recall_history'].append({ 'iter_num': i, 'value': fd_recall, 'elapsed_time': elapsed_time })
            fd_m['f1_history'].append({ 'iter_num': i, 'value': fd_f1, 'elapsed_time': elapsed_time })

            if fd != target_fd:
                continue
            vio_pairs = h['vio_pairs']
            lhs = fd.split(' => ')[0][1:-1].split(', ')
            rhs = fd.split(' => ')[1].split(', ')
            attrs = lhs + rhs
            
            # Check if the violation was caught for short-term memory
            fd_st_vios_marked, fd_st_vios_found, fd_st_vios_total = vioStats(curr_sample, curr_sample, feedback, vio_pairs, attrs, dirty_dataset, clean_dataset)
            st_vios_marked |= fd_st_vios_marked
            st_vios_found |= fd_st_vios_found
            st_vios_total |= fd_st_vios_total
        
        # Normalize Bayesian confidences
        sum_unnormalized_confs = sum([fd_m['conf'] for fd_m in fd_metadata.values()])
        for fd_m in fd_metadata.values():
            fd_m['conf'] = fd_m['conf'] / sum_unnormalized_confs
            fd_m['conf_history'][-1]['value'] = fd_m['conf_history'][-1]['value'] / sum_unnormalized_confs
        
        # Get output from models
        max_h_bayesian = heapq.nlargest(5, fd_metadata.keys(), key=lambda x: fd_metadata[x]['conf'])
        max_h_hp = heapq.nlargest(5, fd_metadata.keys(), key=lambda x: fd_metadata[x]['f1_history'][-1]['value'])
        
        # Hypothesis testing: if FD scores in model output are not sufficiently strong, user does not change their mind
        if np.mean([fd_metadata[mhhp]['f1_history'][-1]['value'] for mhhp in max_h_hp]) < HP_DECISION_THRESHOLD:
            max_h_hp = [max_h] if i == 1 and max_h != 'Not Sure' else [] if i == 1 else study_metrics['hp_prediction'][-1]['value']
        # try:
        #     user_h_in_hp = next(h for h in max_h_hp if h == user_hypothesis_history[i]['value'][0])
        #     if fd_metadata[user_h_in_hp]['f1_history'][-1]['value'] < HP_DECISION_THRESHOLD:
        #         max_h_hp = [max_h] if i == 1 and max_h != 'Not Sure' else [] if i == 1 else study_metrics['hp_prediction'][-1]['value']
        # except:
        #     max_h_hp = [max_h] if i == 1 and max_h != 'Not Sure' else [] if i == 1 else study_metrics['hp_prediction'][-1]['value']
        
        study_metrics['bayesian_prediction'].append({ 'iter_num': i, 'value': max_h_bayesian, 'elapsed_time': elapsed_time })
        study_metrics['hp_prediction'].append({ 'iter_num': i, 'value': max_h_hp, 'elapsed_time': elapsed_time })

        # Calculate rewards for each model configuration
        if user_hypothesis_history[i]['value'][0] != 'Not Sure':
            user_h = user_hypothesis_history[i]['value'][0]
            user_lhs = set(user_h.split(' => ')[0][1:-1].split(', '))
            user_rhs = set(user_h.split(' => ')[1].split(', '))
            try:
                existing_fds = list(fd_metadata.keys())
                existing_fd = next(ef for ef in existing_fds if set(ef.split(' => ')[0][1:-1].split(', ')) == user_lhs and set(ef.split(' => ')[1].split(', ')) == user_rhs)
                user_h = existing_fd
            except StopIteration as e:
                console.log(e)
                return
            
            bayesian_output = [
                {
                    'fd': mhb,
                    'lhs': set(mhb.split(' => ')[0][1:-1].split(', ')),
                    'rhs': set(mhb.split(' => ')[1].split(', '))
                }
                for mhb in max_h_bayesian
            ]
            hp_output = [
                {
                    'fd': mhhp,
                    'lhs': set(mhhp.split(' => ')[0][1:-1].split(', ')),
                    'rhs': set(mhhp.split(' => ')[1].split(', '))
                }
                for mhhp in max_h_hp
            ]

            bayesian_match_1, bayesian_match_mrr_1, bayesian_match_penalty_1, bayesian_match_mrr_penalty_1 = output_reward(user_h, bayesian_output[:1], fd_metadata)            
            bayesian_match_3, bayesian_match_mrr_3, bayesian_match_penalty_3, bayesian_match_mrr_penalty_3 = output_reward(user_h, bayesian_output[:3], fd_metadata)
            bayesian_match_5, bayesian_match_mrr_5, bayesian_match_penalty_5, bayesian_match_mrr_penalty_5 = output_reward(user_h, bayesian_output[:5], fd_metadata)
            hp_match_1, hp_match_mrr_1, hp_match_penalty_1, hp_match_mrr_penalty_1 = output_reward(user_h, hp_output[:1], fd_metadata)
            hp_match_3, hp_match_mrr_3, hp_match_penalty_3, hp_match_mrr_penalty_3 = output_reward(user_h, hp_output[:3], fd_metadata)
            hp_match_5, hp_match_mrr_5, hp_match_penalty_5, hp_match_mrr_penalty_5 = output_reward(user_h, hp_output[:5], fd_metadata)
            
            study_metrics['bayesian_match_1'].append(bayesian_match_1)
            study_metrics['hp_match_1'].append(hp_match_1)
            study_metrics['bayesian_match_mrr_1'].append(bayesian_match_mrr_1)
            study_metrics['hp_match_mrr_1'].append(hp_match_mrr_1)
            study_metrics['bayesian_match_penalty_1'].append(bayesian_match_penalty_1)
            study_metrics['hp_match_penalty_1'].append(hp_match_penalty_1)
            study_metrics['bayesian_match_mrr_penalty_1'].append(bayesian_match_mrr_penalty_1)
            study_metrics['hp_match_mrr_penalty_1'].append(hp_match_mrr_penalty_1)
            
            study_metrics['bayesian_match_3'].append(bayesian_match_3)
            study_metrics['hp_match_3'].append(hp_match_3)
            study_metrics['bayesian_match_mrr_3'].append(bayesian_match_mrr_3)
            study_metrics['hp_match_mrr_3'].append(hp_match_mrr_3)
            study_metrics['bayesian_match_penalty_3'].append(bayesian_match_penalty_3)
            study_metrics['hp_match_penalty_3'].append(hp_match_penalty_3)
            study_metrics['bayesian_match_mrr_penalty_3'].append(bayesian_match_mrr_penalty_3)
            study_metrics['hp_match_mrr_penalty_3'].append(hp_match_mrr_penalty_3)

            study_metrics['bayesian_match_5'].append(bayesian_match_5)
            study_metrics['hp_match_5'].append(hp_match_5)
            study_metrics['bayesian_match_mrr_5'].append(bayesian_match_mrr_5)
            study_metrics['hp_match_mrr_5'].append(hp_match_mrr_5)
            study_metrics['bayesian_match_penalty_5'].append(bayesian_match_penalty_5)
            study_metrics['hp_match_penalty_5'].append(hp_match_penalty_5)
            study_metrics['bayesian_match_mrr_penalty_5'].append(bayesian_match_mrr_penalty_5)
            study_metrics['hp_match_mrr_penalty_5'].append(hp_match_mrr_penalty_5)

        else:
            study_metrics['bayesian_match_1'].append(0)
            study_metrics['hp_match_1'].append(0)
            study_metrics['bayesian_match_mrr_1'].append(0)
            study_metrics['hp_match_mrr_1'].append(0)
            study_metrics['bayesian_match_penalty_1'].append(0)
            study_metrics['hp_match_penalty_1'].append(0)
            study_metrics['bayesian_match_mrr_penalty_1'].append(0)
            study_metrics['hp_match_mrr_penalty_1'].append(0)
            
            study_metrics['bayesian_match_3'].append(0)
            study_metrics['hp_match_3'].append(0)
            study_metrics['bayesian_match_mrr_3'].append(0)
            study_metrics['hp_match_mrr_3'].append(0)
            study_metrics['bayesian_match_penalty_3'].append(0)
            study_metrics['hp_match_penalty_3'].append(0)
            study_metrics['bayesian_match_mrr_penalty_3'].append(0)
            study_metrics['hp_match_mrr_penalty_3'].append(0)

            study_metrics['bayesian_match_5'].append(0)
            study_metrics['hp_match_5'].append(0)
            study_metrics['bayesian_match_mrr_5'].append(0)
            study_metrics['hp_match_mrr_5'].append(0)
            study_metrics['bayesian_match_penalty_5'].append(0)
            study_metrics['hp_match_penalty_5'].append(0)
            study_metrics['bayesian_match_mrr_penalty_5'].append(0)
            study_metrics['hp_match_mrr_penalty_5'].append(0)

        # Medium-term memory violation calculations
        if i > 1:
            for h in h_space:
                fd = h['cfd']
                if fd != target_fd:
                    continue
                vio_pairs = h['vio_pairs']
                lhs = fd.split(' => ')[0][1:-1].split(', ')
                rhs = fd.split(' => ')[1].split(', ')
                attrs = lhs + rhs
                
                fd_st_vios_marked, fd_st_vios_found, fd_st_vios_total = vioStats(curr_sample, mt_sample, feedback, vio_pairs, attrs, dirty_dataset, clean_dataset)
                mt_vios_marked |= fd_st_vios_marked
                mt_vios_found |= fd_st_vios_found
                mt_vios_total |= fd_st_vios_total
        else:
            mt_vios_marked = copy.deepcopy(st_vios_marked)
            mt_vios_found = copy.deepcopy(st_vios_found)
            mt_vios_total = copy.deepcopy(st_vios_total)

        if i > 2:
            for h in h_space:
                fd = h['cfd']
                if fd != target_fd:
                    continue
                vio_pairs = h['vio_pairs']
                lhs = fd.split(' => ')[0][1:-1].split(', ')
                rhs = fd.split(' => ')[1].split(', ')
                attrs = lhs + rhs
                
                fd_st_vios_marked, fd_st_vios_found, fd_st_vios_total = vioStats(curr_sample, mt_2_sample, feedback, vio_pairs, attrs, dirty_dataset, clean_dataset)
                mt_2_vios_marked |= fd_st_vios_marked
                mt_2_vios_found |= fd_st_vios_found
                mt_2_vios_total |= fd_st_vios_total
        else:
            mt_2_vios_marked = copy.deepcopy(mt_vios_marked)
            mt_2_vios_found = copy.deepcopy(mt_vios_found)
            mt_2_vios_total = copy.deepcopy(mt_vios_total)

        if i > 3:
            for h in h_space:
                fd = h['cfd']
                if fd != target_fd:
                    continue
                vio_pairs = h['vio_pairs']
                lhs = fd.split(' => ')[0][1:-1].split(', ')
                rhs = fd.split(' => ')[1].split(', ')
                attrs = lhs + rhs
                
                fd_st_vios_marked, fd_st_vios_found, fd_st_vios_total = vioStats(curr_sample, mt_3_sample, feedback, vio_pairs, attrs, dirty_dataset, clean_dataset)
                mt_3_vios_marked |= fd_st_vios_marked
                mt_3_vios_found |= fd_st_vios_found
                mt_3_vios_total |= fd_st_vios_total
        else:
            mt_3_vios_marked = copy.deepcopy(mt_2_vios_marked)
            mt_3_vios_found = copy.deepcopy(mt_2_vios_found)
            mt_3_vios_total = copy.deepcopy(mt_2_vios_total)
                
        # Long-term memory violation calculations
        if i > 1:
            for h in h_space:
                fd = h['cfd']
                if fd != target_fd:
                    continue
                vio_pairs = h['vio_pairs']
                lhs = fd.split(' => ')[0][1:-1].split(', ')
                rhs = fd.split(' => ')[1].split(', ')
                attrs = lhs + rhs
                
                fd_st_vios_marked, fd_st_vios_found, fd_st_vios_total = vioStats(curr_sample, lt_sample, feedback, vio_pairs, attrs, dirty_dataset, clean_dataset)
                lt_vios_marked |= fd_st_vios_marked
                lt_vios_found |= fd_st_vios_found
                lt_vios_total |= fd_st_vios_total
        else:
            lt_vios_marked = copy.deepcopy(st_vios_marked)
            lt_vios_found = copy.deepcopy(st_vios_found)
            lt_vios_total = copy.deepcopy(st_vios_total)

        # Short, mid, and long-term violation precision, recall, and F1
        if len(st_vios_total) > 0:
            st_vio_recall = len(st_vios_found) / len(st_vios_total)
        else:
            st_vio_recall = 0.5
        
        if len(lt_vios_total) > 0:
            lt_vio_recall = len(lt_vios_found) / len(lt_vios_total)
        else:
            lt_vio_recall = 0.5

        if len(mt_vios_total) > 0:
            mt_vio_recall = len(mt_vios_found) / len(mt_vios_total)
        else:
            mt_vio_recall = 0.5

        if len(mt_2_vios_total) > 0:
            mt_2_vio_recall = len(mt_2_vios_found) / len(mt_2_vios_total)
        else:
            mt_2_vio_recall = 0.5

        if len(mt_3_vios_total) > 0:
            mt_3_vio_recall = len(mt_3_vios_found) / len(mt_3_vios_total)
        else:
            mt_3_vio_recall = 0.5

        if len(st_vios_marked) > 0:
            st_vio_precision = len(st_vios_found) / len(st_vios_marked)
        else:
            st_vio_precision = 0.5

        if len(lt_vios_marked) > 0:
            lt_vio_precision = len(lt_vios_found) / len(lt_vios_marked)
        else:
            lt_vio_precision = 0.5

        if len(mt_vios_marked) > 0:
            mt_vio_precision = len(mt_vios_found) / len(mt_vios_marked)
        else:
            mt_vio_precision = 0.5

        if len(mt_2_vios_marked) > 0:
            mt_2_vio_precision = len(mt_2_vios_found) / len(mt_2_vios_marked)
        else:
            mt_2_vio_precision = 0.5

        if len(mt_3_vios_marked) > 0:
            mt_3_vio_precision = len(mt_3_vios_found) / len(mt_3_vios_marked)
        else:
            mt_3_vio_precision = 0.5

        if st_vio_precision > 0 or st_vio_recall > 0:
            st_vio_f1 = 2 * (st_vio_precision * st_vio_recall) / (st_vio_precision + st_vio_recall)
        else:
            st_vio_f1 = 0
        
        if lt_vio_precision > 0 or lt_vio_recall > 0:
            lt_vio_f1 = 2 * (lt_vio_precision * lt_vio_recall) / (lt_vio_precision + lt_vio_recall)
        else:
            lt_vio_f1 = 0

        if mt_vio_precision > 0 or mt_vio_recall > 0:
            mt_vio_f1 = 2 * (mt_vio_precision * mt_vio_recall) / (mt_vio_precision + mt_vio_recall)
        else:
            mt_vio_f1 = 0

        if mt_2_vio_precision > 0 or mt_2_vio_recall > 0:
            mt_2_vio_f1 = 2 * (mt_2_vio_precision * mt_2_vio_recall) / (mt_2_vio_precision + mt_2_vio_recall)
        else:
            mt_2_vio_f1 = 0

        if mt_3_vio_precision > 0 or mt_3_vio_recall > 0:
            mt_3_vio_f1 = 2 * (mt_3_vio_precision * mt_3_vio_recall) / (mt_3_vio_precision + mt_3_vio_recall)
        else:
            mt_3_vio_f1 = 0

        # Store metric results
        study_metrics['st_vio_recall'].append({ 'iter_num': int(i), 'value': st_vio_recall, 'elapsed_time': elapsed_time })
        study_metrics['mt_vio_recall'].append({ 'iter_num': int(i), 'value': mt_vio_recall, 'elapsed_time': elapsed_time })
        study_metrics['mt_2_vio_recall'].append({ 'iter_num': int(i), 'value': mt_2_vio_recall, 'elapsed_time': elapsed_time })
        study_metrics['mt_3_vio_recall'].append({ 'iter_num': int(i), 'value': mt_3_vio_recall, 'elapsed_time': elapsed_time })
        study_metrics['lt_vio_recall'].append({ 'iter_num': int(i), 'value': lt_vio_recall, 'elapsed_time': elapsed_time })
        study_metrics['st_vio_precision'].append({ 'iter_num': int(i), 'value': st_vio_precision, 'elapsed_time': elapsed_time })
        study_metrics['mt_vio_precision'].append({ 'iter_num': int(i), 'value': mt_vio_precision, 'elapsed_time': elapsed_time })
        study_metrics['mt_2_vio_precision'].append({ 'iter_num': int(i), 'value': mt_2_vio_precision, 'elapsed_time': elapsed_time })
        study_metrics['mt_3_vio_precision'].append({ 'iter_num': int(i), 'value': mt_3_vio_precision, 'elapsed_time': elapsed_time })
        study_metrics['lt_vio_precision'].append({ 'iter_num': int(i), 'value': lt_vio_precision, 'elapsed_time': elapsed_time })
        study_metrics['st_vio_f1'].append({ 'iter_num': int(i), 'value': st_vio_f1, 'elapsed_time': elapsed_time })
        study_metrics['mt_vio_f1'].append({ 'iter_num': int(i), 'value': mt_vio_f1, 'elapsed_time': elapsed_time })
        study_metrics['mt_2_vio_f1'].append({ 'iter_num': int(i), 'value': mt_2_vio_f1, 'elapsed_time': elapsed_time })
        study_metrics['mt_3_vio_f1'].append({ 'iter_num': int(i), 'value': mt_3_vio_f1, 'elapsed_time': elapsed_time })
        study_metrics['lt_vio_f1'].append({ 'iter_num': int(i), 'value': lt_vio_f1, 'elapsed_time': elapsed_time })

        study_metrics['st_vios_marked'].append({ 'iter_num': int(i), 'value': list(st_vios_marked), 'elapsed_time': elapsed_time })
        study_metrics['mt_vios_marked'].append({ 'iter_num': int(i), 'value': list(mt_vios_marked), 'elapsed_time': elapsed_time })
        study_metrics['mt_2_vios_marked'].append({ 'iter_num': int(i), 'value': list(mt_2_vios_marked), 'elapsed_time': elapsed_time })
        study_metrics['mt_3_vios_marked'].append({ 'iter_num': int(i), 'value': list(mt_3_vios_marked), 'elapsed_time': elapsed_time })
        study_metrics['lt_vios_marked'].append({ 'iter_num': int(i), 'value': list(lt_vios_marked), 'elapsed_time': elapsed_time })
        study_metrics['st_vios_found'].append({ 'iter_num': int(i), 'value': list(st_vios_found), 'elapsed_time': elapsed_time })
        study_metrics['mt_vios_found'].append({ 'iter_num': int(i), 'value': list(mt_vios_found), 'elapsed_time': elapsed_time })
        study_metrics['mt_2_vios_found'].append({ 'iter_num': int(i), 'value': list(mt_2_vios_found), 'elapsed_time': elapsed_time })
        study_metrics['mt_3_vios_found'].append({ 'iter_num': int(i), 'value': list(mt_3_vios_found), 'elapsed_time': elapsed_time })
        study_metrics['lt_vios_found'].append({ 'iter_num': int(i), 'value': list(lt_vios_found), 'elapsed_time': elapsed_time })
        study_metrics['st_vios_total'].append({ 'iter_num': int(i), 'value': list(st_vios_total), 'elapsed_time': elapsed_time })
        study_metrics['mt_vios_total'].append({ 'iter_num': int(i), 'value': list(mt_vios_total), 'elapsed_time': elapsed_time })
        study_metrics['mt_2_vios_total'].append({ 'iter_num': int(i), 'value': list(mt_2_vios_total), 'elapsed_time': elapsed_time })
        study_metrics['mt_3_vios_total'].append({ 'iter_num': int(i), 'value': list(mt_3_vios_total), 'elapsed_time': elapsed_time })
        study_metrics['lt_vios_total'].append({ 'iter_num': int(i), 'value': list(lt_vios_total), 'elapsed_time': elapsed_time })

        # Calculate cumulative user precision, recall, and f1 score
        if int(i) > 1:
            found = list()
            marked = list()
            total = list()
            found_set = set()
            marked_set = set()
            total_set = set()

            for it in range(0, len(study_metrics['st_vios_found'])):
                found += study_metrics['st_vios_found'][it]['value']
                marked += study_metrics['st_vios_marked'][it]['value']
                total += study_metrics['st_vios_total'][it]['value']
                found_set |= set(study_metrics['st_vios_found'][it]['value'])
                marked_set |= set(study_metrics['st_vios_marked'][it]['value'])
                total_set |= set(study_metrics['st_vios_total'][it]['value'])

            cumulative_precision = 0.5 if len(marked) == 0 else (len(found)) / (len(marked))
            cumulative_precision_noover = 0.5 if len(marked_set) == 0 else (len(found_set) / len(marked_set))
            cumulative_recall = (len(found)) / (len(total))
            cumulative_recall_noover = (len(found_set) / len(total_set))
        else:
            cumulative_precision = study_metrics['st_vio_precision'][-1]['value']
            cumulative_recall = study_metrics['st_vio_recall'][-1]['value']
            cumulative_precision_noover = study_metrics['st_vio_precision'][-1]['value']
            cumulative_recall_noover = study_metrics['st_vio_recall'][-1]['value']
        
        cumulative_f1 = 0 if cumulative_precision == 0 and cumulative_recall == 0 else (2 * cumulative_precision * cumulative_recall) / (cumulative_precision + cumulative_recall)
        cumulative_f1_noover = 0 if cumulative_precision_noover == 0 and cumulative_recall_noover == 0 else (2 * cumulative_precision_noover * cumulative_recall_noover) / (cumulative_precision_noover + cumulative_recall_noover)
        
        # Save cumulative precision, recall, and f1-score values
        study_metrics['cumulative_precision'].append({ 'iter_num': int(i), 'value': cumulative_precision, 'elapsed_time': elapsed_time })
        study_metrics['cumulative_recall'].append({ 'iter_num': int(i), 'value': cumulative_recall, 'elapsed_time': elapsed_time })
        study_metrics['cumulative_precision_noover'].append({ 'iter_num': int(i), 'value': cumulative_precision_noover, 'elapsed_time': elapsed_time })
        study_metrics['cumulative_recall_noover'].append({ 'iter_num': int(i), 'value': cumulative_recall_noover, 'elapsed_time': elapsed_time })
        study_metrics['cumulative_f1'].append({ 'iter_num': int(i), 'value': cumulative_f1, 'elapsed_time': elapsed_time })
        study_metrics['cumulative_f1_noover'].append({ 'iter_num': int(i), 'value': cumulative_f1_noover, 'elapsed_time': elapsed_time })

    if len(iters) > 0:
        study_metrics['bayesian_match_rate_1'] = np.mean(study_metrics['bayesian_match_1'])
        study_metrics['hp_match_rate_1'] = np.mean(study_metrics['hp_match_1'])
        study_metrics['bayesian_match_rate_mrr_1'] = np.mean(study_metrics['bayesian_match_mrr_1'])
        study_metrics['hp_match_rate_mrr_1'] = np.mean(study_metrics['hp_match_mrr_1'])
        study_metrics['bayesian_match_rate_3'] = np.mean(study_metrics['bayesian_match_3'])
        study_metrics['hp_match_rate_3'] = np.mean(study_metrics['hp_match_3'])
        study_metrics['bayesian_match_rate_mrr_3'] = np.mean(study_metrics['bayesian_match_mrr_3'])
        study_metrics['hp_match_rate_mrr_3'] = np.mean(study_metrics['hp_match_mrr_3'])
        study_metrics['bayesian_match_rate_5'] = np.mean(study_metrics['bayesian_match_5'])
        study_metrics['hp_match_rate_5'] = np.mean(study_metrics['hp_match_5'])
        study_metrics['bayesian_match_rate_mrr_5'] = np.mean(study_metrics['bayesian_match_mrr_5'])
        study_metrics['hp_match_rate_mrr_5'] = np.mean(study_metrics['hp_match_mrr_5'])

        study_metrics['bayesian_match_rate_penalty_1'] = np.mean(study_metrics['bayesian_match_penalty_1'])
        study_metrics['hp_match_rate_penalty_1'] = np.mean(study_metrics['hp_match_penalty_1'])
        study_metrics['bayesian_match_rate_mrr_penalty_1'] = np.mean(study_metrics['bayesian_match_mrr_penalty_1'])
        study_metrics['hp_match_rate_mrr_penalty_1'] = np.mean(study_metrics['hp_match_mrr_penalty_1'])
        study_metrics['bayesian_match_rate_penalty_3'] = np.mean(study_metrics['bayesian_match_penalty_3'])
        study_metrics['hp_match_rate_penalty_3'] = np.mean(study_metrics['hp_match_penalty_3'])
        study_metrics['bayesian_match_rate_mrr_penalty_3'] = np.mean(study_metrics['bayesian_match_mrr_penalty_3'])
        study_metrics['hp_match_rate_mrr_penalty_3'] = np.mean(study_metrics['hp_match_mrr_penalty_3'])
        study_metrics['bayesian_match_rate_penalty_5'] = np.mean(study_metrics['bayesian_match_penalty_5'])
        study_metrics['hp_match_rate_penalty_5'] = np.mean(study_metrics['hp_match_penalty_5'])
        study_metrics['bayesian_match_rate_mrr_penalty_5'] = np.mean(study_metrics['bayesian_match_mrr_penalty_5'])
        study_metrics['hp_match_rate_mrr_penalty_5'] = np.mean(study_metrics['hp_match_mrr_penalty_5'])

    return study_metrics, fd_metadata
