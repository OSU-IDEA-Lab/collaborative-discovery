import requests
import random
from pprint import pprint
import os
import json
import pandas as pd
import numpy as np
import sys
import pickle
import math
import scipy.special as sc
from scipy.stats import beta as betaD
import re

# class Hypothesis(object):
#     def __init__(self, fd, conf, support, vios, vio_pairs):
#         self.fd = fd
#         self.conf = conf
#         self.support = support
#         self.vios = vios
#         self.vio_pairs = vio_pairs

class FDMeta(object):
    def __init__(self, fd, a, b, support, vios, vio_pairs):
        self.lhs = fd.split(' => ')[0][1:-1].split(', ')
        self.rhs = fd.split(' => ')[1].split(', ')
        self.alpha = a
        self.alpha_history = [a]
        self.beta = b
        self.beta_history = [b]
        self.conf = (a / (a+b))
        self.support = support
        self.vios = vios
        self.vio_pairs = vio_pairs

def initialPrior(mu, variance):
    beta = (1 - mu) * ((mu * (1 - mu) / variance) - 1)
    alpha = (mu * beta) / (1 - mu)
    return alpha, beta

def buildFeedbackMap(data, feedback, header):
    feedbackMap = dict()
    cols = header
    for row in data.keys():
        tup = dict()
        for col in cols:
            trimmedCol = re.sub(r'/[\n\r]+/g', '', col)
            cell = next(f for f in feedback if f['row'] == int(data[row]['id']) and f['col'] == trimmedCol)
            tup[col] = cell['marked']
        feedbackMap[row] = tup
    return feedbackMap

def shuffleFDs(fds):
    return random.shuffle(fds)

def run(s, b_type, decision_type, stat_calc):
    if b_type == 'oracle':
        p_max = 0.9
    elif b_type == 'informed':
        p_max = 0.9
    else:
        p_max = 0.5

    if s is None:
        s = '0'

    with open('./scenarios.json', 'r') as f:
        scenarios = json.load(f)
    scenario = scenarios[s]
    target_fd = scenario['target_fd']
    h_space = scenario['hypothesis_space']

    fd_metadata = dict()

    iter_num = 0
    
    for h in h_space:
        if h['cfd'] != target_fd:
            continue
        
        h['vio_pairs'] = set(tuple(vp) for vp in h['vio_pairs'])

        if b_type == 'oracle':
            # conf = next(i for i in scenario['clean_hypothesis_space'] if i['cfd'] == h['cfd'])['conf']
            mu = next(i for i in scenario['clean_hypothesis_space'] if i['cfd'] == h['cfd'])['conf']
            if mu == 1:
                mu = 0.99999
            variance = 0.00000001
            alpha, beta = initialPrior(mu, variance)
            # alpha = 1
            # beta = 1
        elif b_type == 'informed':
            mu = h['conf']
            variance = 0.01
            alpha, beta = initialPrior(mu, variance)
        else:
            alpha = 1
            beta = 1
        
        fd_m = FDMeta(
            fd=h['cfd'],
            a=alpha,
            b=beta,
            support=h['support'],
            vios=h['vios'],
            vio_pairs=h['vio_pairs']
        )
        print('iter:', iter_num)
        print('alpha:', fd_m.alpha)
        print('beta:', fd_m.beta)
        # for i in full_dirty_data.index:
        #     for j in full_dirty_data.index:
        #         if i == j:
        #             continue
        #         match = True
        #         for lh in fd_m.lhs:
        #             if full_dirty_data.at[i, lh] != full_dirty_data.at[j, lh]:
        #                 match = False
        #                 break

        #         if match is True and ((i, j) not in X and (j, i) not in X):
        #             if i < j:
        #                 X.add((i, j))
        #                 X_per_FD[h['cfd']].add((i, j))
        #             else:
        #                 X.add((j, i))
        #                 X_per_FD[h['cfd']].add((j, i))
        fd_metadata[h['cfd']] = fd_m

    project_id = None

    try:
        r = requests.post('http://localhost:5000/duo/api/import', data={
            'scenario_id': str(s),
            'email': '',
            'initial_fd': 'Not Sure',
            'fd_comment': '',
            'skip_user': True,
            'violation_ratio': 'close'
        })
        print(r)
        res = r.json()
        project_id = res['project_id']
    except Exception as e:
        print(e)
        return

    print(project_id)

    data = None
    feedback = None
    sample_X = list()

    try:
        print('before sample')
        r = requests.post('http://localhost:5000/duo/api/sample', data={'project_id': project_id})
        print('after sample')
        res = r.json()

        sample = res['sample']
        print('extracted sample')
        sample_X = set(tuple(x) for x in res['X'])
        print('got vios')
        data = json.loads(sample)
        feedback = json.loads(res['feedback'])
        print('parsed data')
        for row in data.keys():
            for j in data[row].keys():
                if j == 'id':
                    continue
                if data[row][j] is None:
                    data[row][j] = ''
                elif type(data[row][j]) != 'str':
                    data[row][j] = str(data[row][j])
        
        print('prepped data')
    except Exception as e:
        print(e)
        return

    print('initialized feedback object')
    msg = ''
    iter_num = 0

    max_marked = 1
    mark_prob = 0.5

    marked_rows = set()
    vios_marked = set()
    vios_found = set()

    while msg != '[DONE]':
        iter_num += 1
        print('iter:', iter_num)
        print(data.keys())
        header = list()
        for row in data.keys():
            header = [c for c in data[row].keys() if c != 'id']
            break
        feedbackMap = buildFeedbackMap(data, feedback, header)

        # Bayesian behavior
        for fd, fd_m in fd_metadata.items():
            if fd != target_fd:
                continue

            # Step 1: update hyperparameters
            if b_type != 'oracle':
                successes = 0
                failures = 0

                for i in data.keys():
                    if int(i) not in fd_m.vios:
                        successes += 1
                    else:
                        failures += 1

                print('successes:', successes)
                print('failures:', failures)

                fd_m.alpha += successes
                fd_m.alpha_history.append(fd_m.alpha)
                fd_m.beta += failures
                fd_m.beta_history.append(fd_m.beta)
                print('alpha:', fd_m.alpha)
                print('beta:', fd_m.beta)

        # Step 2: mark errors according to new beliefs
        fd_m = fd_metadata[target_fd]
        q_t = fd_m.alpha / (fd_m.alpha + fd_m.beta) if b_type != 'oracle' else fd_m.conf

        iter_marked_rows = {i for i in marked_rows if str(i) in data.keys()}
        iter_vios_marked = {(x,y) for (x,y) in vios_marked if (x != y and (x,y) in sample_X) or (x == y and str(x) in data.keys())}
        iter_vios_found = {(x,y) for (x,y) in vios_found if (x != y and (x,y) in sample_X) or (x == y and str(x) in data.keys())}
        iter_vios_total = {i for i in fd_m.vio_pairs if i in sample_X}

        # print(sample)
        print('q_t:', q_t)

        for row in data.keys():

            # if int(row) in iter_marked_rows:
            #     print(row)
            #     continue

            if b_type == 'oracle':
                if stat_calc == 'precision':
                    q_t = mark_prob
                elif stat_calc == 'recall':
                    if len(iter_vios_marked) >= max_marked:
                        q_t = 0
                else:
                    continue

            vios_w_i = {v for v in iter_vios_total if int(row) in v and v not in iter_vios_marked}

            if decision_type == 'coin-flip':
                decision = np.random.binomial(1, q_t)
            else:
                decision = 1 if q_t >= p_max else 0
            # print(row, decision)

            # if len({v for v in iter_vios_marked if int(row) in v}) > 0:
            #     print('skipped')
            #     continue

            if decision == 1:
                if len(vios_w_i) > 0:
                    for rh in fd_m.rhs:
                        feedbackMap[row][rh] = True
                    vios_found |= vios_w_i
                    iter_vios_found |= vios_w_i
                    vios_marked |= vios_w_i
                    iter_vios_marked |= vios_w_i
                    marked_rows.add(int(row))
                    iter_marked_rows.add(int(row))
                    vios_marked.discard((int(row), int(row)))
                    iter_vios_marked.discard((int(row), int(row)))
                    
                else:
                    for rh in fd_m.rhs:
                        feedbackMap[row][rh] = False
                    vios_marked.discard((int(row), int(row)))
                    iter_vios_marked.discard((int(row), int(row)))
                    marked_rows.discard(int(row))
                    iter_marked_rows.discard(int(row))
            else:
                if len(vios_w_i) > 0:
                    for rh in fd_m.rhs:
                        feedbackMap[row][rh] = False
                    vios_found -= vios_w_i
                    iter_vios_found -= vios_w_i
                    vios_marked -= vios_w_i
                    iter_vios_marked -= vios_w_i
                    marked_rows.discard(int(row))
                    iter_marked_rows.discard(int(row))
                else:
                    for rh in fd_m.rhs:
                        feedbackMap[row][rh] = True
                    vios_marked.add((int(row), int(row)))
                    iter_vios_marked.add((int(row), int(row)))
                    marked_rows.add(int(row))
                    iter_marked_rows.add(int(row))
            
        precision = len(iter_vios_found) / len(iter_vios_marked) if len(iter_vios_marked) > 0 else 1
        recall = len(iter_vios_found) / len(iter_vios_total) if len(iter_vios_total) > 0 else 1
        # print('vios found:', iter_vios_found)
        # print('vios marked:', iter_vios_marked)
        # print('vios total:', iter_vios_total)
        # print('precision:', precision)
        # print('recall:', recall)
                    
        
        feedback = dict()
        for f in feedbackMap.keys():
            feedback[data[f]['id']] = feedbackMap[f]

        is_new_feedback = False
        for idx in feedback.keys():
            for col in feedback[idx].keys():
                if feedback[idx][col] is True:
                    is_new_feedback = True
                    break
            if is_new_feedback is True:
                break
        
        formData = {
            'project_id': project_id,
            'feedback': json.dumps(feedback),
            'current_user_h': 'Not Sure',
            'user_h_comment': '',
        }

        try:
            r = requests.post('http://localhost:5000/duo/api/feedback', data=formData)
            res = r.json()
            msg = res['msg']
            if msg != '[DONE]':
                sample = res['sample']
                sample_X = set(tuple(x) for x in res['X'])
                feedback = json.loads(res['feedback'])
                data = json.loads(sample)

                for row in data.keys():
                    for j in data[row].keys():
                        if j == 'id':
                            continue

                        if data[row][j] is None:
                            data[row][j] = ''
                        elif type(data[row][j]) != 'str':
                            data[row][j] = str(data[row][j])
                if mark_prob < 0.9:
                    mark_prob += 0.05
                elif mark_prob < 0.95:
                    mark_prob += 0.01
                # print(iter_vios_marked)
                if max_marked < 5:
                    max_marked += 1

        except Exception as e:
            print(e)
            msg = '[DONE]'

    pickle.dump( fd_metadata, open('./store/' + project_id + '/fd_metadata.p', 'wb') )

if __name__ == '__main__':
    s = sys.argv[1]
    b_type = sys.argv[2]
    decision_type = sys.argv[3]
    num_runs = int(sys.argv[4])
    stat_calc = None if len(sys.argv) < 6 else sys.argv[5]
    for i in range(0, num_runs):
        run(s, b_type, decision_type, stat_calc)