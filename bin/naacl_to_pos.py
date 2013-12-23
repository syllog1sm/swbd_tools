#!/usr/env/bin python
"""Convert Xian Qian's output to a POS file"""

import plac
from Treebank.PTB import PennTreebank


def min_length(words):
    words = [w for w in words if w not in set(['um', 'uh'])]
    words = ' '.join(words).replace('you know', 'you_know').replace('i mean', 'i_mean').split()
    return len(words) >= 2

def preproc(tokens):
    tokens = [t for t in tokens if t not in set(['um', 'uh'])]
    string = ' '.join(tokens)
    string = string.replace('you/PRP know/VBP', 'you_know/UH')
    string = string.replace('you/PRP know/VB', 'you_know/UH')
    string = string.replace('i/PRP mean/VBP', 'i_mean/UH')
    string = string.replace('i/PRP mean/VB', 'i_mean/UH')
    return string

def main(in_loc, ptb_loc):
    dps_toks = []
    punct = set(['.', ':', ',', ';', 'RRB', 'LRB', '``', "''"]) 
    markup = set(['-DFL-', 'XX'])
    ums = set(['um', 'uh'])
    for line in open(in_loc):
        if not line.strip():
            continue
        pieces = line.split()
        word = pieces[0]
        pos = pieces[1]
        tag = pieces[-1]
        dps_toks.append((word, pos, tag))
    corpus = PennTreebank(path=ptb_loc)
    # Index of sw4004
    test_start = 496
    # Index of sw4155
    test_end = 548
    # Dev start
    dev_start = 598
    dev_end = 650
    i = 0
    for file_idx in range(test_start, test_end):
        file_ = corpus.child(file_idx)
        for sent in file_.children():
            if sent.child(0).label == 'CODE': continue
            words = [w for w in sent.listWords() if not w.isPunct() and not
                     w.isTrace() and w.label not in markup and w.text[-1] != '-']
            if not words:
                continue
            text = words[0].text.lower()
            fluent_sent = []
            for word in words:
                text = word.text.lower()
                old_i = i
                while dps_toks[i][0] != text:
                    i += 1
                if dps_toks[i][2][-1] != 'D' and dps_toks[i][0] not in ums:
                    fluent_sent.append('%s/%s' % (dps_toks[i][0], dps_toks[i][1]))
                i += 1
            if min_length(w.text.lower() for w in words):
                print preproc(fluent_sent)

if __name__ == '__main__':
    plac.call(main)
        
