"""Convert the Switchboard corpus via the NXT XML annotations, instead of the Treebank3
format. The difference is that there's no issue of aligning the dps files etc."""
import os.path
from pathlib import Path

import plac
import fabric.api

import Treebank.PTB


def get_dfl(word, sent):
    turn = '%s%s' % (sent.speaker, sent.turnID[1:])
    dfl = [turn, '1' if word.isEdited() else '0', str(word.start_time), str(word.end_time)]
    return '|'.join(dfl)


def speechify(sent):
    for word in sent.listWords():
        if word.parent() is None or word.parent().parent() is None:
            continue
        if word.text == '?':
            word.prune()
        if word.isPunct() or word.isTrace() or word.isPartial():
            word.prune()
        word.text = word.text.lower()


def remove_repairs(sent):
    for node in sent.depthList():
        if node.label == 'EDITED':
            node.prune()


def remove_fillers(sent):
    for word in sent.listWords():
        if word.label == 'UH':
            word.prune()



def remove_prn(sent):
    for node in sent.depthList():
        if node.label != 'PRN':
            continue
        words = [w.text for w in node.listWords()]
        if words == ['you', 'know'] or words == ['i', 'mean']:
            node.prune()


def prune_empty(sent):
    for node in sent.depthList():
        if not node.listWords():
            try:
                node.prune()
            except:
                print node
                print sent
                raise


def convert_to_conll(sents, name):
    """Run the Stanford dependency converter over the mrg file, via the temp
    files /tmp/*.mrg and /tmp/*.dep"""
    mrg_strs = []
    for sent in sents:
        if not sent.listWords():
            mrg_strs.append('(S (SYM -EMPTY-) )')
        else:
            mrg_strs.append(str(sent))
    mrg_str = u'\n'.join(mrg_strs)
    loc = '/tmp/%s.mrg' % name[:-4]
    out_loc = '/tmp/%s.dep' % name[:-4] 
    open(loc, 'w').write(mrg_str)
    cmd = 'java -mx800m -cp "./*:" ' + \
           'edu.stanford.nlp.trees.EnglishGrammaticalStructure ' + \
              '-treeFile "{mrg_loc}" -basic -makeCopulaHead -conllx > {out_loc}'
    # Fabric just gives a nice context-manager for "cd" here
    with fabric.api.lcd('stanford_converter/'):
        # And a nice way to just run something --- I hate subprocess...
        fabric.api.local(cmd.format(mrg_loc=loc, out_loc=out_loc))
    return Path(out_loc).open().read()


def transfer_heads(orig_words, sent, heads, labels):
    tokens = []
    wordID_to_new_idx = dict((w.wordID, i) for i, w in enumerate(sent.listWords()))
    new_idx_to_old_idx = dict((wordID_to_new_idx[token[0]], i) for i, token in
                              enumerate(orig_words) if token[0] in wordID_to_new_idx)
    for i, (wordID, text, pos, dfl) in enumerate(orig_words):
        if wordID in wordID_to_new_idx:
            head_in_new = heads[wordID_to_new_idx[wordID]]
            if head_in_new == 0:
                head = head_in_new
            else:
                head = new_idx_to_old_idx[head_in_new - 1] + 1
            label = labels[wordID_to_new_idx[wordID]]
        else:
            head = i
            label = 'erased'
        assert head >= 0
        tokens.append((text, pos, head, label, dfl))
    return tokens


def do_section(ptb_files, out_dir, name):
    out_dir = Path(out_dir)
    conll = out_dir.join('%s.conll' % name).open('w')
    pos = out_dir.join('%s.pos' % name).open('w')
    txt = out_dir.join('%s.txt' % name).open('w')

    for file_ in ptb_files:
        sents = []
        orig_words = []
        for sent in file_.children():
            speechify(sent)
            orig_words.append([(w.wordID, w.text, w.label, get_dfl(w, sent))
                              for w in sent.listWords()])
            remove_repairs(sent)
            remove_fillers(sent)
            remove_prn(sent)
            prune_empty(sent)
            sents.append(sent)
        conll_strs = convert_to_conll(sents, file_.filename)
        tok_id = 0
        for i, conll_sent in enumerate(conll_strs.strip().split('\n\n')):
            heads, labels = read_conll(conll_sent)
            tokens = transfer_heads(orig_words[i], sents[i], heads, labels)
            conll.write(format_sent(tokens))
            pos.write(u' '.join('%s/%s' % (token[0], token[1]) for token in tokens))
            txt.write(u' '.join(token[0] for token in tokens))
            conll.write(u'\n\n')
            pos.write(u'\n')
            txt.write(u'\n')


def read_conll(dep_txt):
    """Get heads and labels"""
    heads = []; labels = []
    for line in dep_txt.split('\n'):
        if not line.strip():
            continue
        fields = line.split()
        heads.append(int(fields[6]))
        labels.append(fields[7])
    return heads, labels


def format_sent(tokens):
    lines = []
    for i, (text, pos, head, label, dfl) in enumerate(tokens):
        fields = [i + 1, text, '-', pos, pos, dfl, head, label, '-', '-']
        lines.append('\t'.join(str(f) for f in fields))
    return u'\n'.join(lines)


def main(nxt_loc, out_dir):
    corpus = Treebank.PTB.NXTSwitchboard(path=nxt_loc)
    do_section(corpus.train_files(), out_dir, 'train')
    do_section(corpus.dev_files(), out_dir, 'dev')
    do_section(corpus.dev2_files(), out_dir, 'dev2')
    do_section(corpus.eval_files(), out_dir, 'test')


if __name__ == '__main__':
    plac.call(main)
