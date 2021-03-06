import json
import pickle
import os
from helpers import FDMeta
from api import User
import sys

def pkl2jsonRecursive(run_type):
    path = './docker-out/' if run_type == 'real' else './store/'
    project_ids = os.listdir(path)
    # if run_type == 'real':
    obj = pickle.load( open('study-utils/users.p', 'rb') )
    for user in obj.keys():
        obj[user] = obj[user].asdict()
    with open('study-utils/users.json', 'w') as fp:
        json.dump(obj, fp, ensure_ascii=False, indent=4)

    for project_id in project_ids:
        files = os.listdir(path + project_id + '/')
        for f in files:
            print(path + project_id + '/' + f)
            if '.p' in f:
                obj = pickle.load( open(path + project_id + '/' + f, 'rb') )
                if type(obj) == dict:
                    if f == 'fd_metadata.p':
                        for k in obj.keys():
                            obj[k] = obj[k].asdict()
                    elif f == 'interaction_metadata.p':
                        for idx in obj['feedback_history'].keys():
                            for col in obj['feedback_history'][idx].keys():
                                obj['feedback_history'][idx][col] = [i.asdict() for i in obj['feedback_history'][idx][col]]
                        if 'user_hypothesis_history' in obj.keys():
                            obj['user_hypothesis_history'] = [i.asdict() for i in obj['user_hypothesis_history']]
                        obj['sample_history'] = [i.asdict() for i in obj['sample_history']]
                    elif f == 'study_metrics.p':
                        for idx in obj.keys():
                            obj[idx] = [i.asdict() for i in obj[idx]]

                    with open(path + project_id + '/' + f.split('.')[0] + '.json', 'w') as fp:
                        json.dump(obj, fp, ensure_ascii=False, indent=4)

if __name__ == '__main__':
    pkl2jsonRecursive(sys.argv[1])
