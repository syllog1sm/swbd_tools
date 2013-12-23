"""
Given .dep files make the train/dev/test split for SWBD
"""
import plac
from pathlib import Path
from Treebank.PTB import PTBFile

def convert_conll(conll_text):
    lines = []
    for line in conll_text.split():
        if not line.strip():
            lines.append('')
        else:
            pieces = line.split()
            lines.append((pieces[0], pieces[1], int(pieces[6]) - 1, pieces[7]))
    return '\n'.join(lines)

def add_edits(deps, ptb_sents):
    ptb_sents = [sent for sent in ptb_sents[1:] if sent.child(0).label != 'CODE']
    dep_sents = deps.strip().split('\n\n')
    assert len(dep_sents) == len(ptb_sents), '%d vs %d' % (len(dep_sents), len(ptb_sents))
    new_sents = []
    for dep_sent, ptb_sent in zip(dep_sents, ptb_sents):
        edits = set()
        nontrace = [w for w in ptb_sent.listWords() if not w.isTrace()]
        ids = dict((word, i) for i, word in enumerate(nontrace))
        for node in ptb_sent.depthList():
            if node.label == 'EDITED':
                for word in node.listWords():
                    if word.isTrace(): continue
                    edits.add(ids[word])
        new_sent = []
        for i, word in enumerate(dep_sent.split('\n')):
            if i in edits:
                new_sent.append(word[:-1] + 'True')
            else:
                new_sent.append(word[:-1] + 'False')
        new_sents.append('\n'.join(new_sent))
    return '\n\n'.join(new_sents) + '\n\n'


def main(in_dir, out_dir):
    in_dir = Path(in_dir)
    out_dir = Path(out_dir)
    train_file = out_dir.join('train.txt').open('w')
    dev_file = out_dir.join('devr.txt').open('w')
    test_file = out_dir.join('testr.txt').open('w')
    ptb_loc = Path('/usr/local/data/Penn3/parsed/mrg/swbd/')
    for loc in in_dir:
        filename = loc.parts[-1]
        if not filename.endswith('dep'):
            continue
        filenum = int(filename[2:-8])
        if filenum < 4000:
            out_file = train_file
        elif filenum >= 4004 and filenum < 4153:
            out_file = test_file
        elif filenum  >= 4519 and filenum < 4936:
            out_file = dev_file
        if filenum > 4000:
            section = '4'
        elif filenum > 3000:
            section = '3'
        else:
            section = '2'
        ptb_file = PTBFile(path=str(ptb_loc.join(section).join(filename[:-4])))
        try:
            with_edits = add_edits(loc.open().read(), list(ptb_file.children()))
        except AssertionError:
            print "Skipping", loc
            continue
        out_file.write(with_edits)
    train_file.close()
    test_file.close()
    dev_file.close()

if __name__ == '__main__':
    plac.call(main)
