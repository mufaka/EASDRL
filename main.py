#!/usr/bin/env python
# -*- coding: UTF-8 -*-
################################################################################
# Project:  Extracting Action Sequences Based on Deep Reinforcement Learning
# Module:   main
# Author:   Wenfeng Feng 
# Time:     2017.12
################################################################################

import time
import ipdb
import pickle
import argparse
import tensorflow.compat.v1 as tf

from utils import get_time, plot_results, str2bool, print_args
from Agent import Agent
from EADQN import DeepQLearner
# from KerasEADQN import DeepQLearner
from Environment import Environment
from ReplayMemory import ReplayMemory
from gensim.models import KeyedVectors
# from keras.backend.tensorflow_backend import set_session

tf.disable_v2_behavior()

def preset_args():
    """
    Preset args
    """
    parser = argparse.ArgumentParser()

    envarg = parser.add_argument_group('Environment')
    envarg.add_argument("--domain",         type=str,       default='cooking',  help="One of 'win2k', 'cooking' and 'wikihow'")
    envarg.add_argument("--model_dim",      type=str,       default=50,         help="Dimension of the pretrained word vectors (word2vec model)")
    envarg.add_argument("--num_words",      type=int,       default=500,        help="Maximum number of words in a text")
    envarg.add_argument("--word_dim",       type=int,       default=50,         help="Dimension of word embedding")
    envarg.add_argument("--tag_dim",        type=int,       default=50,         help="Dimension of tag embedding")
    envarg.add_argument("--dis_dim",        type=int,       default=50,         help="Dimension of distance embedding")
    envarg.add_argument("--pos_dim",        type=int,       default=50,         help="Dimension of part-of-speech embedding")
    envarg.add_argument("--context_len",    type=int,       default=100,        help="Maximum number of words in the context (of an action name)")
    envarg.add_argument("--reward_assign",  type=list,      default=[1, 2, 3],  help="Reward for essential, optional and exclusive items")
    envarg.add_argument("--reward_base",    type=float,     default=50.0,       help="For reward scaling")
    envarg.add_argument("--object_rate",    type=float,     default=0.07,       help="Percentage of action arguments, a priori")
    envarg.add_argument("--action_rate",    type=float,     default=0.10,       help="Percentage of action names, a priori")
    envarg.add_argument("--use_act_rate",   type=str2bool,  default=True,       help="Whether or not use action_rate, for name extractor")
    envarg.add_argument("--use_act_att",    type=str2bool,  default=False,      help="Whether or not use the given action name to compute attention, for arguments extractor")
    envarg.add_argument("--use_pos",        type=str2bool,  default=True,       help="Whether or not use the part-of-speech of words as input")
    
    memarg = parser.add_argument_group('Replay memory')
    memarg.add_argument("--positive_rate",      type=float,     default=0.9,    help="Percentage of positive samples in a minibatch")
    memarg.add_argument("--priority",           type=str2bool,  default=True,   help="Whether or not apply prioritized sampling")
    memarg.add_argument("--save_replay",        type=str2bool,  default=False,  help="Whether or not save the replay memory")
    memarg.add_argument("--load_replay",        type=str2bool,  default=False,  help="Whether or not load last replay memory")
    memarg.add_argument("--replay_size",        type=int,       default=50000,  help="Size of the replay memory")
    memarg.add_argument("--save_replay_size",   type=int,       default=1000,   help="Size of the replay memory to be saved")
    memarg.add_argument("--save_replay_name",   type=str,       default='data/saved_replay_memory.pkl', help="Directory of saved replay memory")

    netarg = parser.add_argument_group('Deep Q-learning network')
    netarg.add_argument("--batch_size",     type=int,   default=32,     help="Size of minibatch")
    netarg.add_argument("--num_filters",    type=int,   default=32,     help="Number of convolutional filters")
    netarg.add_argument("--dense_dim",      type=int,   default=256,    help="Dimension of the last but two fully-connected layer")
    netarg.add_argument("--num_actions",    type=int,   default=2,      help="Number of actions")
    netarg.add_argument("--optimizer",      type=str,   default='adam', help="Optimizer")
    netarg.add_argument("--learning_rate",  type=float, default=0.001,  help="Learning rate")
    netarg.add_argument("--dropout",        type=float, default=0.25,   help="Dropout rate")
    netarg.add_argument("--gamma",          type=float, default=0.9,    help="Discount factor")

    antarg = parser.add_argument_group('Agent')
    antarg.add_argument("--exploration_rate_start",     type=float,     default=1,      help="Initial exploration probability for training")
    antarg.add_argument("--exploration_rate_end",       type=float,     default=0.1,    help="Final exploration probability for training")
    antarg.add_argument("--exploration_rate_test",      type=float,     default=0.0,    help="Exploration probability for testing")
    antarg.add_argument("--exploration_decay_steps",    type=int,       default=1000,   help="How many time steps to anneal exploration probability")
    antarg.add_argument("--train_frequency",            type=int,       default=1,      help="Train model after 'train_frequency' time steps")
    antarg.add_argument("--train_repeat",               type=int,       default=1,      help="How many bathes to train at a time step")
    antarg.add_argument("--target_steps",               type=int,       default=5,      help="Copy main network to target network after 'target_steps' time steps")
    antarg.add_argument("--random_play",                type=str2bool,  default=False,  help="Play randomly or not")
    antarg.add_argument("--display_training_result",    type=str2bool,  default=True,   help="Whether or not display the F1 scores after each episode")
    antarg.add_argument("--filter_act_ind",             type=str2bool,  default=True,   help="Whether or not neglact the words of action names when extracting action arguments")

    mainarg = parser.add_argument_group('Main loop')
    mainarg.add_argument("--gui_mode",              type=str2bool,  default=False,  help="Whether or not in the human-agent interaction environment")
    mainarg.add_argument("--gpu_fraction",          type=float,     default=0.2,    help="Fraction of GPU memory to use")
    mainarg.add_argument("--epochs",                type=int,       default=20,     help="Training epochs")
    mainarg.add_argument("--start_epoch",           type=int,       default=0,      help="Training from this epoch")
    mainarg.add_argument("--stop_epoch_gap",        type=int,       default=5,      help="Early stop if no improvement after 'stop_epoch_gap' epochs")
    mainarg.add_argument("--train_episodes",        type=int,       default=50,     help="Test once after training 'train_episodes' texts")
    mainarg.add_argument("--load_weights",          type=str2bool,  default=False,  help="Load weights or not")
    mainarg.add_argument("--save_weights",          type=str2bool,  default=True,   help="Save weights or not")
    mainarg.add_argument("--fold_id",               type=int,       default=0,      help="Which fold of data to be trained")
    mainarg.add_argument("--start_fold",            type=int,       default=0,      help="Start training from this fold of data")
    mainarg.add_argument("--end_fold",              type=int,       default=5,      help="End training after this fold of data")
    mainarg.add_argument("--k_fold",                type=int,       default=5,      help="Number of folds, usually 10 or 5")
    mainarg.add_argument("--result_dir",            type=str,       default='test', help="File name for saving results")
    mainarg.add_argument("--agent_mode",            type=str,       default='act',  help="One of 'act' (name extractor) and 'arg' (arguments extractor)")
    
    return parser.parse_args()


def args_init(args):
    """
    args initialization
    """
    args.word2vec = KeyedVectors.load_word2vec_format('data/wordvec_dim%d'%args.model_dim, binary=True)
    if args.load_weights:
        args.exploration_rate_start = args.exploration_rate_end
    if args.agent_mode == 'arg':
        args.num_words = 100
        args.train_episodes = 1000
        args.display_training_result = 0
    args.k_fold_indices = 'data/indices/%s_%s_%d_fold_indices.pkl' % (args.domain, args.agent_mode, args.k_fold)
    args.result_dir = 'results/%s_%s_%s' % (args.domain, args.agent_mode, args.result_dir)
    if args.end_fold > args.k_fold or args.end_fold <= 0:
        args.end_fold = args.k_fold
    return args



def main(args):
    """
    main function, build, train, validate, save and load model
    """
    start = time.time()
    print('Current time is: %s' % get_time())
    print('Starting at main...')
    # store k-fold cross-validation results, including recall, precision, f1 and average reward
    fold_result = {'rec': [], 'pre': [], 'f1': [], 'rw': []}

    # one can continue to train model from the start_fold rather than fold 0 
    for fi in range(args.start_fold, args.end_fold):
        fold_start = time.time()
        args.fold_id = fi
        if args.fold_id == args.start_fold:
            # Initialize environment and replay memory
            env_act = Environment(args, args.agent_mode)
            mem_act = ReplayMemory(args, args.agent_mode)
        else:
            env_act.get_fold_data(args.fold_id)
            mem_act.reset()
        gpu_options = tf.GPUOptions(per_process_gpu_memory_fraction=args.gpu_fraction)
        # set_session(tf.Session(config=tf.ConfigProto(gpu_options=gpu_options))) # for keras
        with tf.Session(config=tf.ConfigProto(gpu_options=gpu_options)) as sess:
            # ipdb.set_trace()
            # Initialize deep_q_net and agent
            net_act = DeepQLearner(args, sess, args.agent_mode)
            agent = Agent(env_act, mem_act, net_act, args)

            # loop over epochs
            epoch_result = {'rec': [0.0], 'pre': [0.0], 'f1': [0.0], 'rw': [0.0]}
            training_result = {'rec': [], 'pre': [], 'f1': [], 'loss': [], 'rw': []}
            log_epoch = 0
            with open("%s_fold%d.txt" % (args.result_dir, args.fold_id), 'w') as outfile:
                # print all args to the screen and outfile
                print_args(args, outfile)

                if args.load_weights:
                    print('Loading weights ...')
                    filename = 'weights/%s_%s_%d_fold%d.h5' % (args.domain, args.agent_mode, args.k_fold, args.fold_id)
                    net_act.load_weights(filename)  

                for epoch in range(args.start_epoch, args.start_epoch + args.epochs):
                    # test the model every args.train_episodes or at the end of an epoch
                    num_test = -1
                    env_act.train_epoch_end_flag = False
                    while not env_act.train_epoch_end_flag:
                        # training
                        num_test += 1
                        restart_init = False if num_test > 0 else True
                        tmp_result = agent.train(args.train_steps, args.train_episodes, restart_init)
                        for k in training_result:
                            training_result[k].extend(tmp_result[k])
                        # testing
                        rec, pre, f1, rw = agent.test(args.valid_steps, outfile)

                        if f1 > max(epoch_result['f1']):
                            if args.save_weights:
                                filename = 'weights/%s_%s_%d_fold%d.h5' % (args.domain, args.agent_mode, args.k_fold, args.fold_id)
                                net_act.save_weights(filename)

                            epoch_result['f1'].append(f1)
                            epoch_result['rec'].append(rec)
                            epoch_result['pre'].append(pre)
                            epoch_result['rw'].append(rw)
                            log_epoch = epoch
                            outfile.write('\n\n Best f1 score: {}  best epoch: {}\n'.format(epoch_result, log_epoch))
                            print('\n\n Best f1 score: {}  best epoch: {}\n'.format(epoch_result, log_epoch))
                    
                    # if no improvement after args.stop_epoch_gap, break
                    if epoch - log_epoch >= args.stop_epoch_gap:
                        outfile.write('\n\nBest f1 score: {}  best epoch: {}\n'.format(epoch_result, log_epoch))
                        print('\nepoch: %d  result_dir: %s' % (epoch, args.result_dir))
                        print('-----Early stopping, no improvement after %d epochs-----\n' % args.stop_epoch_gap)
                        break
                if args.save_replay:
                    mem_act.save(args.save_replay_name, args.save_replay_size)
                
                # plot the training process results if you want
                # filename = '%s_fold%d_training_process.pdf'%(args.result_dir, args.fold_id)
                # plot_results(epoch_result, args.domain, filename)
                # outfile.write('\n\n training process:\n{}\n\n'.format(epoch_result))

                # find out the best f1 score in the current fold, add it to fold_result
                best_ind = epoch_result['f1'].index(max(epoch_result['f1']))
                for k in epoch_result:
                    fold_result[k].append(epoch_result[k][best_ind])
                    outfile.write('{}: {}\n'.format(k, fold_result[k]))
                    print(('{}: {}\n'.format(k, fold_result[k])))
                # compute the average f1 and average reward of all fold results up to now
                avg_f1 = sum(fold_result['f1']) / len(fold_result['f1'])
                avg_rw = sum(fold_result['rw']) / len(fold_result['rw'])
                outfile.write('\nAvg f1: {}  Avg reward: {}\n'.format(avg_f1, avg_rw))
                print('\nAvg f1: {}  Avg reward: {}\n'.format(avg_f1, avg_rw))
                
                fold_end = time.time()
                print('Total time cost of fold %d is: %ds' % (args.fold_id, fold_end - fold_start))
                outfile.write('\nTotal time cost of fold %d is: %ds\n' % (args.fold_id, fold_end - fold_start))
        
        tf.reset_default_graph()
    end = time.time()
    print('Total time cost: %ds' % (end - start))
    print('Current time is: %s\n' % get_time())




if __name__ == '__main__':
    args = args_init(preset_args())
    main(args)

