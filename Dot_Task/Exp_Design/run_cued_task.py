"""
runprobContextTask
"""

import webbrowser
import numpy as np
from psychopy import event
from Dot_Task.Exp_Design.make_config import ProbContextConfig
from Dot_Task.Exp_Design.prob_context_task import probContextTask
from Dot_Task.Exp_Design.utils import get_difficulties

# ****************************************************************************
# set-up variables
# ****************************************************************************
print('Enter the subject ID')
subject_code = raw_input('subject id: ')

save_dir = '../Data' 
cuename = 'cued_dot_task'
cue_type = 'deterministic'
# set up task variables
stim_repetitions = 5
recursive_p = .9
# window variables
win_kwargs = {'fullscr': False,
              'screen': 1,
              'size': [1920, 1200]}
# counterbalance ts_order (which ts is associated with top of screen)
ts_order = ['motion','orientation']
np.random.shuffle(ts_order)



# ****************************************************************************
# set up config files
# ****************************************************************************
# load motion_difficulties and ori_difficulties from adaptive tasks
difficulties = get_difficulties(subject_code)
if difficulties['motion'] == {}:
    difficulties['motion'] = {
     ('in', 'easy'): 0.05,
     ('in', 'hard'): 0.01,
     ('out', 'easy'): 0.05,
     ('out', 'hard'): 0.01}
    
if difficulties['orientation'] == {}:
     difficulties['orientation'] = {
     (-60, 'easy'): 25,
     (-60, 'hard'): 15,
     (30, 'easy'): 25,
     (30, 'hard'): 15}   
     
# cued task 
cue_config = ProbContextConfig(taskname=cuename, 
                               subjid=subject_code, 
                               stim_repetitions=stim_repetitions, 
                               ts_order=ts_order, 
                               rp=recursive_p,
                               motion_difficulties=difficulties['motion'],
                               ori_difficulties=difficulties['orientation'])
cue_config_file = cue_config.get_config()

    

# setup tasks
cued_task=probContextTask(cue_config_file,
                          subject_code, 
                          save_dir=save_dir,
                          cue_type=cue_type,
                          win_kwargs=win_kwargs)


# ****************************************************************************
# ************** RUN TASK ****************************************************
# ****************************************************************************

# ****************************************************************************
# Start cueing
# ****************************************************************************

intro_text = \
    """
    In this phase of the experiment you will be cued
    whether to pay attention to motion or orientation
    before each trial.
    
    Please wait for the experimenter.
    """

cued_task.run_task(intro_text=intro_text)    
          
#************************************
# Determine payment
#************************************
points,trials = cued_task.getPoints()
performance = (float(points)/trials-.25)/.75
pay_bonus = round(performance*5)
print('Participant ' + subject_code + ' won ' + str(points) + ' points out of ' + str(trials) + ' trials. Bonus: $' + str(pay_bonus))

#open post-task questionnaire
webbrowser.open_new('https://stanforduniversity.qualtrics.com/SE/?SID=SV_9KzEWE7l4xuORIF')






