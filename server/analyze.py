from pprint import pprint
import os
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import sys
import csv
import pickle
import math
import statistics
from operator import attrgetter
from collections import Counter

from helpers import StudyMetric

class PHGivenX(object):
    def __init__(self, h, value):
        self.h = h
        self.value = value

def wHeuristicUniform(cfd):
    lhs = cfd.split(' => ')[0][1:-1].split(', ')
    weights = {lh: 1/len(lhs) for lh in lhs}
    return weights

def bayes(sampling_method):
    with open('scenarios.json') as f:
        all_scenarios = json.load(f)
    scenario_ids = [k for k, s in all_scenarios.items() if s['sampling_method'] == sampling_method]

    project_ids = [d for d in os.listdir('./store') if os.path.isdir(os.path.join('./store/', d))]
    for project_id in project_ids:
        with open('./store/' + project_id + '/project_info.json') as f:
            project_info = json.load(f)
        scenario_id = project_info['scenario_id']
        if scenario_id not in scenario_ids:
            break
        
        modeling_metadata = pickle.load( open('./store/' + project_id + '/modeling_metadata.p', 'rb') )
        cfd_metadata = pickle.load( open('./store/' + project_id + '/cfd_metadata.p', 'rb') )
        bayes_modeling_metadata = modeling_metadata
        bayes_modeling_metadata['p_Y_in_C_given_X'] = dict()
        iter_count = pickle.load( open('./store/' + project_id + '/current_iter.p', 'rb') )

        # P(h)        
        for cfd in cfd_metadata.keys():
            # UNIFORM ATTRIBUTE WEIGHTS
            wUniform = wHeuristicUniform(cfd)   # p(h)
            phUniform = np.prod([v for _, v in wUniform.items()])
            bayes_modeling_metadata['p_h']['hUniform'][cfd] = phUniform

        for heur in bayes_modeling_metadata['p_h'].keys():
            bayes_modeling_metadata['p_Y_in_C_given_X'][heur] = list()
            for it in range(1, iter_count+1):
                elapsed_time = bayes_modeling_metadata['Y'][it].elapsed_time
                discovered_cfds = [cfd for cfd in bayes_modeling_metadata['p_X_given_h'].keys() if it in [x.iter_num for x in bayes_modeling_metadata['p_X_given_h'][cfd]]]
                if len(discovered_cfds) == 0:
                    # P(Y in C | X)
                    bayes_modeling_metadata['p_Y_in_C_given_X'][heur].append(StudyMetric(iter_num=it, value=0, elapsed_time=elapsed_time))
                    
                else:
                    p_h_given_X_list = list()
                    for h in discovered_cfds:
                        # p(h | X)
                        elem = [x for x in bayes_modeling_metadata['p_X_given_h'][h] if x.iter_num == it].pop()
                        # print(elem.value)
                        # elapsed_time = elem.elapsed_time
                        p_X_given_h = elem.value
                        p_h = bayes_modeling_metadata['p_h'][heur][h]
                        p_h_given_X = p_X_given_h * p_h
                        p_h_given_X_list.append(PHGivenX(h=h, value=p_h_given_X))
                    
                    # normalized p(h | X) such that sum of all p(h | X) = 1
                    p_h_given_X_list_sum = sum([x.value for x in p_h_given_X_list])
                    # print(p_h_given_X_list_sum)
                    p_h_given_X_list = [PHGivenX(h=x.h, value=((x.value/p_h_given_X_list_sum) if x.value > 0 else 0)) for x in p_h_given_X_list]

                    # p(Y in C | X)
                    p_Y_in_C_given_X = 1
                    for y in bayes_modeling_metadata['Y'][it-1].value:
                        p_y_in_C_given_X = 0 # p(y in C | X)
                        for phgx in p_h_given_X_list:
                            h = phgx.h
                            p_h_given_X = phgx.value
                            i_y_supp_h = bayes_modeling_metadata['y_supp_h'][h][y]  # I(y in supp(h))
                            p_y_in_C_given_X += (i_y_supp_h * p_h_given_X)
                            
                        p_Y_in_C_given_X *= p_y_in_C_given_X
                        print('p(Y in C | X) =', p_Y_in_C_given_X)
                    
                    bayes_modeling_metadata['p_Y_in_C_given_X'][heur].append(StudyMetric(iter_num=it, value=p_Y_in_C_given_X, elapsed_time=elapsed_time))

        pickle.dump( bayes_modeling_metadata, open('./store/' + project_id + '/bayes_modeling_metadata.p', 'wb') )


def max_likelihood(sampling_method):
    with open('scenarios.json') as f:
        all_scenarios = json.load(f)
    scenario_ids = [k for k, s in all_scenarios.items() if s['sampling_method'] == sampling_method]

    project_ids = [d for d in os.listdir('./store') if os.path.isdir(os.path.join('./store/', d))]
    for project_id in project_ids:
        with open('./store/' + project_id + '/project_info.json') as f:
            project_info = json.load(f)
        scenario_id = project_info['scenario_id']
        if scenario_id not in scenario_ids:
            break
        
        modeling_metadata = pickle.load( open('./store/' + project_id + '/modeling_metadata.p', 'rb') )
        cfd_metadata = pickle.load( open('./store/' + project_id + '/cfd_metadata.p', 'rb') )
        min_modeling_metadata = modeling_metadata
        min_modeling_metadata['p_Y_in_C_given_X'] = dict()
        iter_count = pickle.load( open('./store/' + project_id + '/current_iter.p', 'rb') )

        # P(h)        
        for cfd in cfd_metadata.keys():
            # UNIFORM ATTRIBUTE WEIGHTS
            wUniform = wHeuristicUniform(cfd)   # p(h)
            phUniform = np.prod([v for _, v in wUniform.items()])
            min_modeling_metadata['p_h']['hUniform'][cfd] = phUniform

        for heur in min_modeling_metadata['p_h'].keys():
            min_modeling_metadata['p_Y_in_C_given_X'][heur] = list()
            for it in range(1, iter_count+1):
                elapsed_time = min_modeling_metadata['Y'][it].elapsed_time
                discovered_cfds = [cfd for cfd in min_modeling_metadata['p_X_given_h'].keys() if it in [x.iter_num for x in min_modeling_metadata['p_X_given_h'][cfd]]]
                if len(discovered_cfds) == 0:
                    # P(Y in C | X)
                    min_modeling_metadata['p_Y_in_C_given_X'][heur].append(StudyMetric(iter_num=it, value=0, elapsed_time=elapsed_time))
                    
                else:
                    # h_ML
                    max_p_X_given_h = 0
                    h_ML = None
                    for cfd in discovered_cfds:
                        # print(cfd)
                        curr_p_X_given_h = [x.value for x in min_modeling_metadata['p_X_given_h'][cfd] if x.iter_num == it].pop()
                        # print(curr_p_X_given_h)
                        if max_p_X_given_h <= curr_p_X_given_h:
                            max_p_X_given_h = curr_p_X_given_h
                            h_ML = cfd
                
                    # p(h_ML | X)
                    elem = [x for x in min_modeling_metadata['p_X_given_h'][h_ML] if x.iter_num == it].pop()
                    p_X_given_h_ML = elem.value
                    p_h_ML = min_modeling_metadata['p_h'][heur][h_ML]
                    p_h_ML_given_X = p_X_given_h_ML * p_h_ML

                    # p(Y in C | X)
                    p_Y_in_C_given_X = 1
                    for y in min_modeling_metadata['Y'][it-1].value:
                        # p_y_in_C_given_X = 0 # p(y in C | X)
                        # for phgx in p_h_given_X_list:
                            # h = phgx.h
                            # p_h_given_X = phgx.value
                        i_y_supp_h_ML = min_modeling_metadata['y_supp_h'][h_ML][y]  # I(y in supp(h_ML))
                        p_y_in_C_given_X = (i_y_supp_h_ML * p_h_ML_given_X)
                        p_Y_in_C_given_X *= p_y_in_C_given_X
                        print('p(Y in C | X) =', p_Y_in_C_given_X)
                    
                    min_modeling_metadata['p_Y_in_C_given_X'][heur].append(StudyMetric(iter_num=it, value=p_Y_in_C_given_X, elapsed_time=elapsed_time))

        pickle.dump( min_modeling_metadata, open('./store/' + project_id + '/min_modeling_metadata.p', 'wb') )