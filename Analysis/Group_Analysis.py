"""
Created on Mon Apr 27 11:16:08 2015

@author: Ian
"""

import numpy as np
from scipy.stats import norm
import pandas as pd
import matplotlib.pyplot as plt
from Load_Data import load_data
from helper_classes import BiasPredModel
from helper_functions import *
import statsmodels.api as sm
import pickle, glob, re, lmfit, os
import seaborn as sns
from ggplot import *
from collections import OrderedDict as odict


#*********************************************
# Set up defaults
#*********************************************

font = {'family' : 'normal',
        'weight' : 'normal',
        'size'   : 20,
        }
        
axes = {'titleweight' : 'bold'
        }
plt.rc('font', **font)
plt.rc('axes', **axes)

plot = False
save = True
#choose whether the model has a variable bias term
bias = True

#*********************************************
# Load Data
#*********************************************
home = os.path.expanduser("~")
if bias == True:
    try:
        fit_dict = pickle.load(open('Analysis_Output/bias_parameter_fits.p','rb'))
    except:
        fit_dict = {}
else:
    try:
        fit_dict = pickle.load(open('Analysis_Output/nobias_parameter_fits.p','rb'))
    except:
        fit_dict = {}
try:
    midline_fit_dict = pickle.load(open('Analysis_Output/midline_parameter_fits.p','rb'))
except:
    midline_fit_dict = {}
    
group_behavior = {}
gtrain_df = pd.DataFrame()
gtest_df = pd.DataFrame()
gtaskinfo = []

train_files = glob.glob(home + '/MEGA/IanE_RawData/Prob_Context_Task/RawData/*Context_20*yaml')
test_files = glob.glob(home + '/MEGA/IanE_RawData/Prob_Context_Task/RawData/*Context_test*yaml')
    
count = 0
for train_file, test_file in zip(train_files,test_files):
    count += 1
    if count != 0:
        pass #continue
    train_name = re.match(r'.*/RawData.([0-9][0-9][0-9].*).yaml', train_file).group(1)
    test_name = re.match(r'.*/RawData.([0-9][0-9][0-9].*).yaml', test_file).group(1)
    subj_name = re.match(r'.*/RawData.(\w*)_Prob*', test_file).group(1)
    print(subj_name)
    try:
        train_dict = pickle.load(open('../Data/' + train_name + '.p','rb'))
        taskinfo, train_dfa = [train_dict.get(k) for k in ['taskinfo','dfa']]
    
    except FileNotFoundError:
        train_taskinfo, train_dfa = load_data(train_file, train_name, mode = 'train')
        train_dict = {'taskinfo': train_taskinfo, 'dfa': train_dfa}
        pickle.dump(train_dict, open('../Data/' + train_name + '.p','wb'))
        
    try:
        test_dict = pickle.load(open('../Data/' + test_name + '.p','rb'))
        taskinfo, test_dfa = [test_dict.get(k) for k in ['taskinfo','dfa']]
    except FileNotFoundError:
        taskinfo, test_dfa = load_data(test_file, test_name, mode = 'test')
        test_dict = {'taskinfo': taskinfo, 'dfa': test_dfa}
        pickle.dump(test_dict, open('../Data/' + test_name + '.p','wb'))



#*********************************************
# Preliminary Setup
#*********************************************

    
    recursive_p = taskinfo['recursive_p']
    states = taskinfo['states']
    state_dis = [norm(states[0]['c_mean'], states[0]['c_sd']), norm(states[1]['c_mean'], states[1]['c_sd']) ]
    ts_order = [states[0]['ts'],states[1]['ts']]
    ts_dis = [state_dis[i] for i in ts_order]
    ts2_side = np.sign(ts_dis[1].mean())
    taskinfo['ts2_side'] = ts2_side
    #To ensure TS2 is always associated with the 'top' of the screen, or positive
    #context values, flip the context values if this isn't the case.
    #This ensures that TS1 is always the shape task-set and, for analysis purposes,
    #always associated with the bottom of the screen
    train_dfa['true_context'] = train_dfa['context']
    test_dfa['true_context'] = test_dfa['context']
    
    if ts2_side == -1:
        train_dfa['context'] = train_dfa['context']* -1
        test_dfa['context'] = test_dfa['context']* -1
        ts_dis = ts_dis [::-1]
        
    #What was the mean contextual value for each taskset during this train run?
    train_ts_means = list(train_dfa.groupby('ts').agg(np.mean).context)
    #Same for standard deviation
    train_ts_std = list(train_dfa.groupby('ts').agg(np.std).context)
    train_ts_dis = [norm(m,s) for m,s in zip(train_ts_means,train_ts_std)]
    #And do the same for recursive_p
    train_recursive_p = 1- train_dfa.switch.mean()
    
    
    #decompose contexts
    test_dfa['abs_context'] = abs(test_dfa.context)    
    train_dfa['abs_context'] = abs(train_dfa.context)
    train_dfa['context_sign'] = np.sign(train_dfa.context)
    test_dfa['context_sign'] = np.sign(test_dfa.context)
    #Create vector of context differences
    test_dfa['context_diff'] = test_dfa['context'].diff()
    
    #transform rt
    train_dfa['log_rt'] = np.log(train_dfa.rt)
    test_dfa['log_rt'] = np.log(test_dfa.rt)
    
    #*********************************************
    # Model fitting
    #*********************************************
    
    

    if subj_name + '_fullRun' not in fit_dict.keys():
        #Fitting Functions
        def bias_fitfunc(rp, tsb, df):
            init_prior = [.5,.5]
            model = BiasPredModel(train_ts_dis, init_prior, ts_bias = tsb, recursive_prob = rp)
            model_likelihoods = []
            for i in df.index:
                c = df.context[i]
                trial_choice = df.subj_ts[i]
                conf = model.calc_posterior(c)
                model_likelihoods.append(conf[trial_choice])
            return np.array(model_likelihoods)

        def bias_errfunc(params,df):
            rp = params['rp']
            tsb = params['tsb']
            #minimize
            return abs(np.sum(np.log(bias_fitfunc(rp,tsb,df)))) #single value

        

        #Fit bias model
        #attempt to simplify:
        fit_params = lmfit.Parameters()
        fit_params.add('rp', value = .6, min = 0, max = 1)
        if bias == True:
            fit_params.add('tsb', value = 1, min = 0)
        else:
            fit_params.add('tsb', value = 1, vary = False, min = 0)
        out = lmfit.minimize(bias_errfunc,fit_params, method = 'lbfgsb', kws= {'df': test_dfa})
        lmfit.report_fit(out)
        fit_dict[subj_name + '_fullRun'] = out.values
    
    
    #fit midline rule random probability:
    if subj_name + '_fullRun' not in midline_fit_dict.keys():
        #Fitting Functions
        def midline_errfunc(params,df):
            eps = params['eps'].value
            context_sgn = np.array([max(i,0) for i in df.context_sign])
            choice = df.subj_ts
            #minimize
            return -np.sum(np.log(abs(abs(choice - (1-context_sgn))-eps)))
            
        #Fit bias model
        #attempt to simplify:
        fit_params = lmfit.Parameters()
        fit_params.add('eps', value = .1, min = 0, max = 1)
        midline_out = lmfit.minimize(midline_errfunc,fit_params, method = 'lbfgsb', kws= {'df': test_dfa})
        lmfit.report_fit(midline_out)
        midline_fit_dict[subj_name + '_fullRun'] = midline_out.values
    
    #*********************************************
    # Set up observers
    #*********************************************
    
    #**************TRAIN*********************
    
    #This observer know the exact statistics of the task, always chooses correctly
    #given that it chooses the correct task-set, and perfectly learns from feedback.
    #This means that it sets the prior probability for each ts to the transition probabilities
    #of the correct task-set on each trial (which a subject 'could' do due to the
    #deterministic feedback). Basically, after receiving FB, the ideal observer
    #knows exactly what task it is in and should act accordingly.
    observer_prior = [.5,.5]
    observer_choices = []
    for i,trial in train_dfa.iterrows():
        c = trial.context
        ts = trial.ts
        conf= calc_posterior(c,observer_prior,ts_dis)    
        obs_choice = np.argmax(conf)
        observer_choices.append(obs_choice)
        observer_prior = np.round([.9*(1-ts)+.1*ts,.9*ts+.1*(1-ts)],2)
        
    train_dfa['opt_observer_choices'] = observer_choices
    train_dfa['opt_observer_switch'] = abs((train_dfa.opt_observer_choices).diff())
    train_dfa['conform_opt_observer'] = np.equal(train_dfa.subj_ts, observer_choices)
    
    #Optimal observer for train, without feedback     
    no_fb_observer = BiasPredModel(train_ts_dis, [.5,.5], ts_bias = 1, recursive_prob = train_recursive_p)
    observer_choices = []
    posteriors = []
    for i,trial in train_dfa.iterrows():
        c = trial.context
        posteriors.append(no_fb_observer.calc_posterior(c)[1])
    posteriors = np.array(posteriors)
    train_dfa['no_fb_observer_posterior'] = posteriors
    train_dfa['opt_observer_choices'] = (posteriors>.5).astype(int)
    train_dfa['no_fb_observer_switch'] = (train_dfa.no_fb_observer_posterior>.5).diff()
    train_dfa['conform_no_fb_observer'] = np.equal(train_dfa.subj_ts, posteriors>.5)
    
    
    #**************TEST*********************
    
    #Bias observer for test    
    params = fit_dict[subj_name + '_fullRun']
    fit_observer = BiasPredModel(train_ts_dis, [.5,.5], ts_bias = params['tsb'], recursive_prob = params['rp'])
    #Fit observer for test        
    observer_choices = []
    posteriors = []
    for i,trial in test_dfa.iterrows():
        c = trial.context
        posteriors.append(fit_observer.calc_posterior(c)[1])
    posteriors = np.array(posteriors)

    test_dfa['fit_observer_posterior'] = posteriors
    test_dfa['fit_observer_choices'] = (posteriors>.5).astype(int)
    test_dfa['fit_observer_switch'] = (test_dfa.fit_observer_posterior>.5).diff()
    test_dfa['conform_fit_observer'] = np.equal(test_dfa.subj_ts, posteriors>.5)
    test_dfa['fit_certainty'] = (abs(test_dfa.fit_observer_posterior-.5))/.5
    
    #Optimal observer for test        
    optimal_observer = BiasPredModel(train_ts_dis, [.5,.5], ts_bias = 1, recursive_prob = train_recursive_p)
    observer_choices = []
    posteriors = []
    for i,trial in test_dfa.iterrows():
        c = trial.context
        posteriors.append(optimal_observer.calc_posterior(c)[1])
    posteriors = np.array(posteriors)
    
    test_dfa['opt_observer_posterior'] = posteriors
    test_dfa['opt_observer_choices'] = (posteriors>.5).astype(int)
    test_dfa['opt_observer_switch'] = (test_dfa.opt_observer_posterior>.5).diff()
    test_dfa['conform_opt_observer'] = np.equal(test_dfa.subj_ts, posteriors>.5)
    test_dfa['opt_certainty'] = (abs(test_dfa.opt_observer_posterior-.5))/.5


    #Ignore observer for test        
    ignore_observer = BiasPredModel(train_ts_dis, [.5,.5], ts_bias = 1, recursive_prob = .5)
    observer_choices = []
    posteriors = []
    for i,trial in test_dfa.iterrows():
        c = trial.context
        posteriors.append(ignore_observer.calc_posterior(c)[1])
    posteriors = np.array(posteriors)
    test_dfa['ignore_observer_posterior'] = posteriors
    test_dfa['ignore_observer_choices'] = (posteriors>.5).astype(int)
    test_dfa['ignore_observer_switch'] = (test_dfa.ignore_observer_posterior>.5).diff()
    test_dfa['conform_ignore_observer'] = np.equal(test_dfa.subj_ts, posteriors>.5)

    train_dfa['id'] = subj_name
    test_dfa['id'] = subj_name
    gtrain_df = pd.concat([gtrain_df,train_dfa])
    gtest_df = pd.concat([gtest_df,test_dfa])   
    gtaskinfo.append(taskinfo)

 
gtaskinfo = pd.DataFrame(gtaskinfo)

#Exclude subjects where stim_confom is below some threshold 
select_ids = gtest_df.groupby('id').mean().stim_conform>.75
select_ids = select_ids[select_ids]
select_rows = [i in select_ids for i in gtrain_df.id]
gtrain_df = gtrain_df[select_rows]
select_rows = [i in select_ids for i in gtest_df.id]
gtest_df = gtest_df[select_rows]
ids = select_ids.index

#separate learner group
select_ids = gtest_df.groupby('id').mean().correct > .55
select_ids = select_ids[select_ids]
select_rows = [i in select_ids for i in gtrain_df.id]
gtrain_learn_df = gtrain_df[select_rows]
select_rows = [i in select_ids for i in gtest_df.id]
gtest_learn_df = gtest_df[select_rows]
learn_ids = select_ids.index

if save == True:
    if bias == True:
        pickle.dump(fit_dict,open('Analysis_Output/bias_parameter_fits.p','wb'))
    else:
        pickle.dump(fit_dict,open('Analysis_Output/nobias_parameter_fits.p','wb'))
    pickle.dump(midline_fit_dict,open('Analysis_Output/midline_parameter_fits.p','wb'))
    gtest_learn_df.to_csv('Analysis_Output/gtest_learn_df.csv')
    
#*********************************************
# Switch Analysis
#*********************************************
#Count the number of times there was a switch to each TS for each context value
switch_counts = odict()
switch_counts['ignore_observer'] = gtest_learn_df.query('ignore_observer_switch == True').groupby(['ignore_observer_choices','context']).trial_count.count().unstack(level = 0)
switch_counts['subject'] = gtest_learn_df.query('subj_switch == True').groupby(['subj_ts','context']).trial_count.count().unstack(level = 0)
switch_counts['opt_observer'] = gtest_learn_df.query('opt_observer_switch == True').groupby(['opt_observer_choices','context']).trial_count.count().unstack(level = 0)
try:
    switch_counts['fit_observer'] = gtest_learn_df.query('fit_observer_switch == True').groupby(['fit_observer_choices','context']).trial_count.count().unstack(level = 0)
except:
    print("No fit observer!")

#normalize switch counts by the ignore rule. The ignore rule represents
#the  number of switches someone would make if they switched task-sets
#every time the stimuli's position crossed the ignore to that position
norm_switch_counts = odict()
for key in switch_counts:
    empty_df = pd.DataFrame(index = np.unique(gtest_df.context), columns = [0,1])
    empty_df.index.name = 'context'
    empty_df.loc[switch_counts[key].index] = switch_counts[key]
    switch_counts[key] = empty_df
    norm_switch_counts[key] = switch_counts[key].div(switch_counts['ignore_observer'],axis = 0)

  
#*********************************************
# Plotting
#*********************************************

contexts = np.unique(gtest_df.context)
figdims = (16,12)
fontsize = 20
plot_df = gtest_learn_df.copy()
plot_df['rt'] = plot_df['rt']*1000
plot_ids = learn_ids
if plot == True:
    
    #Plot task-set count by context value
    p1 = plt.figure(figsize = figdims)
    plt.hold(True) 
    plt.plot(plot_df.groupby('context').subj_ts.mean(), lw = 3, color = 'r', label = 'subject')
    plt.plot(plot_df.groupby('context').fit_observer_choices.mean(), lw = 3, color = 'c', label = 'bias observer')
    plt.plot(plot_df.groupby('context').opt_observer_choices.mean(), lw = 3, color = 'c', ls = '--', label = 'optimal observer')
    plt.plot(plot_df.groupby('context').ignore_observer_choices.mean(), lw = 3, color = 'c', ls = ':', label = 'midline rule')
    plt.xticks(list(range(12)),contexts)
    plt.axvline(5.5, lw = 5, ls = '--', color = 'k')
    plt.xlabel('Stimulus Vertical Position', size = fontsize)
    plt.ylabel('STS choice %', size = fontsize)
    pylab.legend(loc='best',prop={'size':20})
    for subj in ids:
        subj_df = plot_df.query('id == "%s"' %subj)
        if subj_df.correct.mean() < .6:
            plt.plot(subj_df.groupby('context').subj_ts.mean(), lw = 2, color = 'r', alpha = .1)
        else:
            plt.plot(subj_df.groupby('context').subj_ts.mean(), lw = 2, color = 'k', alpha = .1)
    

    #Plot task-set count by context value
    p2 = plt.figure(figsize = figdims)
    plt.hold(True) 
    plt.xticks(list(range(12)),contexts)
    plt.axvline(5.5, lw = 5, ls = '--', color = 'k')
    plt.xlabel('Stimulus Vertical Position', size = fontsize)
    plt.ylabel('STS choice %', size = fontsize)
    for subj in plot_ids[0:5]:
        subj_df = plot_df.query('id == "%s"' %subj)
        plt.plot(subj_df.groupby('context').subj_ts.mean(), lw = 2,  alpha = 1, label = subj_df.id[0])
    plt.gca().set_color_cycle(None)
    for subj in plot_ids[0:5]:
        subj_df = plot_df.query('id == "%s"' %subj)
        plt.plot(subj_df.groupby('context').fit_observer_choices.mean(), lw = 2, ls = '--', alpha = 1)
    pylab.legend(loc='best',prop={'size':20})
        
    #plot distribution of switches, by task-set
    p3 = plt.figure(figsize = figdims)
    plt.subplot(2,1,1)
    plt.hold(True) 
    sub = switch_counts['subject']
    plt.plot(sub[0], lw = 4, color = 'm', label = 'switch to CTS')
    plt.plot(sub[1], lw = 4, color = 'c', label = 'switch to STS')
    sub = switch_counts['fit_observer']
    plt.plot(sub[0], lw = 4, color = 'm', ls = '-.', label = 'bias observer')
    plt.plot(sub[1], lw = 4, color = 'c', ls = '-.')
    sub = switch_counts['opt_observer']
    plt.plot(sub[0], lw = 4, color = 'm', ls = '--', label = 'optimal observer')
    plt.plot(sub[1], lw = 4, color = 'c', ls = '--')
    sub = switch_counts['ignore_observer']
    plt.plot(sub[0], lw = 4, color = 'm', ls = ':', label = 'midline rule')
    plt.plot(sub[1], lw = 4, color = 'c', ls = ':')
    plt.xticks(list(range(12)),np.round(list(sub.index),2))
    plt.axvline(5.5, lw = 5, ls = '--', color = 'k')
    plt.xlabel('Stimulus Vertical Position', size = fontsize)
    plt.ylabel('Switch Counts', size = fontsize)
    pylab.legend(loc='upper right',prop={'size':20})
    for subj in plot_ids:
        subj_df = plot_df.query('id == "%s"' %subj)
        subj_switch_counts = odict()
        subj_switch_counts['ignore_observer'] = subj_df.query('ignore_observer_switch == True').groupby(['ignore_observer_choices','context']).trial_count.count().unstack(level = 0)
        subj_switch_counts['subject'] = subj_df.query('subj_switch == True').groupby(['subj_ts','context']).trial_count.count().unstack(level = 0)
        subj_switch_counts['opt_observer'] = subj_df.query('opt_observer_switch == True').groupby(['opt_observer_choices','context']).trial_count.count().unstack(level = 0)
        
        #normalize switch counts by the ignore rule. The ignore rule represents
        #the  number of switches someone would make if they switched task-sets
        #every time the stimuli's position crossed the ignore to that position
        subj_norm_switch_counts = odict()
        for key in subj_switch_counts:
            empty_df = pd.DataFrame(index = np.unique(subj_df.context), columns = [0,1])
            empty_df.index.name = 'context'
            empty_df.loc[switch_counts[key].index] = subj_switch_counts[key]
            subj_switch_counts[key] = empty_df*len(ids)
            subj_norm_switch_counts[key] = subj_switch_counts[key].div(subj_switch_counts['ignore_observer'],axis = 0)
        sub = subj_switch_counts['subject']
        plt.plot(sub[0], lw = 3, color = 'm', alpha = .10)
        plt.plot(sub[1], lw = 3, color = 'c', alpha = .10)
    
    
        
    #As above, using normalized measure
    plt.subplot(2,1,2)
    plt.hold(True) 
    sub = norm_switch_counts['subject']
    plt.plot(sub[0], lw = 4, color = 'm', label = 'switch to CTS')
    plt.plot(sub[1], lw = 4, color = 'c', label = 'switch to STS')
    sub = norm_switch_counts['fit_observer']
    plt.plot(sub[0], lw = 4, color = 'm',  ls = '-.', label = 'bias observer')
    plt.plot(sub[1], lw = 4, color = 'c', ls = '-.')
    sub = norm_switch_counts['opt_observer']
    plt.plot(sub[0], lw = 4, color = 'm', ls = '--', label = 'optimal observer')
    plt.plot(sub[1], lw = 4, color = 'c', ls = '--')
    sub = norm_switch_counts['ignore_observer']
    plt.plot(sub[0], lw = 4, color = 'm', ls = ':', label = 'midline rule')
    plt.plot(sub[1], lw = 4, color = 'c', ls = ':')
    plt.xticks(list(range(12)),np.round(list(sub.index),2))
    plt.axvline(5.5, lw = 5, ls = '--', color = 'k')
    plt.xlabel('Stimulus Vertical Position', size = fontsize)
    plt.ylabel('Normalized Switch Counts', size = fontsize)
    pylab.ylim([-1,3])
    for subj in plot_ids:
        subj_df = plot_df.query('id == "%s"' %subj)
        subj_switch_counts = odict()
        subj_switch_counts['ignore_observer'] = subj_df.query('ignore_observer_switch == True').groupby(['ignore_observer_choices','context']).trial_count.count().unstack(level = 0)
        subj_switch_counts['subject'] = subj_df.query('subj_switch == True').groupby(['subj_ts','context']).trial_count.count().unstack(level = 0)
        subj_switch_counts['opt_observer'] = subj_df.query('opt_observer_switch == True').groupby(['opt_observer_choices','context']).trial_count.count().unstack(level = 0)
        
        #normalize switch counts by the ignore rule. The ignore rule represents
        #the  number of switches someone would make if they switched task-sets
        #every time the stimuli's position crossed the ignore to that position
        subj_norm_switch_counts = odict()
        for key in subj_switch_counts:
            empty_df = pd.DataFrame(index = np.unique(subj_df.context), columns = [0,1])
            empty_df.index.name = 'context'
            empty_df.loc[switch_counts[key].index] = subj_switch_counts[key]
            subj_switch_counts[key] = empty_df*len(ids)
            subj_norm_switch_counts[key] = subj_switch_counts[key].div(subj_switch_counts['ignore_observer'],axis = 0)
        sub = subj_norm_switch_counts['subject']
        plt.plot(sub[0], lw = 3, color = 'm', alpha = .10)
        plt.plot(sub[1], lw = 3, color = 'c', alpha = .10)


    #look at RT
    p4 = plt.figure(figsize = figdims)
    plt.subplot(4,1,1)
    plot_df.rt.hist(bins = 25)
    plt.ylabel('Frequency', size = fontsize)
    
    plt.subplot(4,1,2)    
    plt.hold(True)
    sns.kdeplot(plot_df.query('subj_switch == 0')['rt'],color = 'm', lw = 5, label = 'stay')
    sns.kdeplot(plot_df.query('subj_switch == 1')['rt'],color = 'c', lw = 5, label = 'switch')
    plot_df.query('subj_switch == 0')['rt'].hist(bins = 25, alpha = .4, color = 'm', normed = True)
    plot_df.query('subj_switch == 1')['rt'].hist(bins = 25, alpha = .4, color = 'c', normed = True)
    pylab.legend(loc='upper right',prop={'size':20})
    plt.xlim(xmin = 0)

    
    plt.subplot(4,1,3)
    plt.hold(True)
    sns.kdeplot(plot_df.query('subj_switch == 0 and rep_resp == 1')['rt'], color = 'm', lw = 5, label = 'repeat response')
    sns.kdeplot(plot_df.query('subj_switch == 0 and rep_resp == 0')['rt'], color = 'c', lw = 5, label = 'change response (within task-set)')
    plot_df.query('subj_switch == 0 and rep_resp == 1')['rt'].hist(bins = 25, alpha = .4, color = 'm', normed = True)
    plot_df.query('subj_switch == 0 and rep_resp == 0')['rt'].hist(bins = 25, alpha = .4, color = 'c', normed = True)
    plt.ylabel('Probability Density', size = fontsize)
    pylab.legend(loc='upper right',prop={'size':20})
    plt.xlim(xmin = 0)

        
    plt.subplot(4,1,4)
    plt.hold(True)
    sns.kdeplot(plot_df.query('subj_ts == 0')['rt'], color = 'm', lw = 5, label = 'ts1')
    sns.kdeplot(plot_df.query('subj_ts == 1')['rt'], color = 'c', lw = 5, label = 'ts2')
    plot_df.query('subj_ts == 0')['rt'].hist(bins = 25, alpha = .4, color = 'm', normed = True)
    plot_df.query('subj_ts == 1')['rt'].hist(bins = 25, alpha = .4, color = 'c', normed = True)
    plt.xlabel('Reaction Time (ms)', size = fontsize)
    pylab.legend(loc='upper right',prop={'size':20})
    plt.xlim(xmin = 0)

    	    
    #RT for switch vs stay for different trial-by-trial context diff
    p5 = plot_df.groupby(['subj_switch','context_diff']).mean().rt.unstack(level = 0).plot(marker = 'o',color = ['c','m'], figsize = figdims, fontsize = fontsize)     
    p5 = p5.get_figure()
           
    #Plot rt against optimal model certainty
    #Take out RT < 100 ms
    opt_conf_rt_p = ggplot(plot_df.query('rt>100'), aes('opt_certainty', 'log_rt')) + geom_point(color = 'coral') + geom_smooth(method = 'lm')
    fit_conf_rt_p = ggplot(plot_df.query('rt>100'), aes('fit_certainty', 'log_rt')) + geom_point(color = 'coral') + geom_smooth(method = 'lm') \
		+ xlab('Model Confidence') + ylab('Log Reaction Time') + xlim(-.05,1.05)
		
    #split by id
    opt_conf_rt_id_p = ggplot(plot_df.query('rt>100'), aes('opt_certainty', 'log_rt', color = 'id')) + geom_point() + geom_smooth(method = 'lm')
    fit_conf_rt_id_p = ggplot(plot_df.query('rt>100'), aes('fit_certainty', 'log_rt', color = 'id')) + geom_point() + geom_smooth(method = 'lm')  \
    	+ xlab('Model Confidence') + ylab('Log Reaction Time') + xlim(-.05,1.05)

    #Plot rt against absolute context
    rt_abs_con_p = ggplot(plot_df.query('rt>100'), aes('abs_context', 'log_rt', color = 'id')) + geom_point() + geom_smooth(method = 'lm') \
        + xlab('Distance From Center') + ylab('Log Reaction Time') + xlim(-.05,1.05)
            
    
    if save == True:
        ggsave(fit_conf_rt_p, '../Plots/Fit_Certainty_vs_RT.pdf', format = 'pdf')
        ggsave(fit_conf_rt_id_p, '../Plots/Fit_Certainty_vs_RT_ids.pdf', format = 'pdf')
        ggsave(rt_abs_con_p, '../Plots/Context_vs_RT_id.pdf', format = 'pdf')
        p1.savefig('../Plots/TS2%_vs_context.pdf', format = 'pdf')
        p2.savefig('../Plots/Individual_subject_fits.pdf',format = 'pdf')
        p3.savefig('../Plots/TS_proportions.pdf', format = 'pdf')
        p4.savefig('../Plots/RTs.pdf', format = 'pdf')
        p5.savefig('../Plots/RT_across_context_diffs.pdf', format = 'pdf')
    
