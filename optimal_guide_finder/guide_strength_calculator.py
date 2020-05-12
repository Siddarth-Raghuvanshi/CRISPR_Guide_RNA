import math
import time
from multiprocessing import Process, Queue, Pool
import numpy as np
import pandas as pd
from optimal_guide_finder.cas_model import CasModel

NT_POS = {'A':0, 'T':1, 'C':2, 'G':3}

def initalize_model(guide_info, filename, num_threads=None):
    """
    return a pandas dataframe with all the data:
        - same order as dictionary + source and target position in the beginning
    """
    #creating the model
    __start = time.time()
    print("Creating Model...")
    model = CasModel(filename)
    __elasped = (time.time() - __start)
    print("Time Model Building: {:.2f}".format(__elasped))

    #Process the guides
    info_df = pd.DataFrame()
    print("Processing Guides...")
    __start = time.time()

    pool = Pool(processes=num_threads)
    results = []
    for gene in guide_info:
        for i, guide in enumerate(guide_info[gene][0]):
            guide_data = pd.Series([guide, gene, guide_info[gene][1][i], guide_info[gene][2][i]],
                                   index=["Guide Sequence", "Gene/ORF Name", "Location in Gene", "Strand"])

            # call
            res = pool.apply_async(process_guide, (model, guide, i))
            results.append(res)
            info_df = info_df.append(guide_data, ignore_index=True)

    pool.close()

    # pull results from the queue
    result_df = pd.DataFrame()
    for res in results:
        result_df = result_df.append(res.get(), ignore_index=True)

    results_df = pd.merge(info_df, result_df, on='Guide Sequence')

    __elasped = (time.time() - __start)
    print("Time Spent Analysing Guides: {:.2f}".format(__elasped))

    return results_df

def process_guide(model, guide, guide_index):

    num_guide = np.array([NT_POS[nt] for nt in list(guide)])
    partition_function = 1

    result = []

    for (source, _) in model.genome_dictionary.items():

        for full_pam in model.get_all_pams():
            dg_pam = model.calc_dg_pam(full_pam)
            dg_supercoiling = model.calc_dg_supercoiling(sigma_initial=-0.05, target_seq=20 * "N")

            for (target_sequence, target_position) in model.genome_dictionary[source][full_pam]:
                np_target_sequence = np.array([NT_POS[nt] for nt in list(target_sequence)])
                dg_exchange = model.calc_dg_exchange(num_guide, np_target_sequence)
                dg_target = dg_pam + dg_supercoiling + dg_exchange

                result.append([target_sequence, math.exp(-dg_target / model.RT)])
                partition_function += math.exp(-dg_target / model.RT)

    result.insert(0,[guide,partition_function])
    guide_series = process_off_target_guides(result)
    print(guide_series)

    return guide_series

def process_off_target_guides(guide_data, verbose=False):
    guide_seq = guide_data[0][0]
    partition_function = guide_data[0][1]
    guide_entropy = 0
    exact_matches = 0
    for off_target in guide_data[1:]:
        if guide_seq == off_target[0]:
            exact_matches += 1 
        probability = off_target[1]/partition_function
        guide_entropy -= probability*np.log2(probability)
    guide_series = pd.Series([guide_seq,
                              guide_entropy,
                              exact_matches],
                             index = ["Guide Sequence",
                                      "Entropy Score",
                                      "Number of Exact Matches"])
    return guide_series

