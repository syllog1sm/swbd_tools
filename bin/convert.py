"""All-in-one SWBD conversion script.

1. Divide .mrg filenames into train/dev/test split
(For each mrg file)
2. Pre-process the file, removing CODE lines, header data etc
3. Fix POS tags, taking the first tag from ^ and | sets.
4. Run the dependency converter over the file, getting back a list of dep trees
5. Add a column marking which tokens are under EDITED nodes
6. Add a column marking the .dps annotations, with the tags RDM/ITM/RPR, DISC,
   FILL and CJ
7. Remove extra tokens: marked XX, -DFL-, punct.
8. Lower-case the text.
9. Remove "um" and "uh", and retokenise you_know and i_mean
9. Remove 1 token sentences.
10. Write the train/dev/test files.

Further processing:
    - clean_dfls.py: Produce a CoNLL-format file with the disfluencies cleaned
                     from it.
    - conll_to_dps.py: Produce .dps files from CoNLL format.
"""
import re
import fabric.api
from pathlib import Path
import plac
from Treebank.PTB import PTBFile


PUNCT = set([',', ':', '.', ';', 'RRB', 'LRB', '``', "''"])
UHS = set(['uh', 'um']) 


class Token(object):
    def __init__(self, line):
        props = line.split()
        self.id = int(props[0]) 
        self.word = props[1]
        self.pos = props[3]
        if self.pos.startswith('^'):
            self.pos = self.pos[1:]
        self.pos = self.pos.split('^')[0]
        self.label = props[7]
        self.head = int(props[6])
        self.is_edit = props[-1] == 'True'
        self.dps_tag = '-'
        self.dps_rm = False
        self.dps_rr = False
        self.mrg_rm = False
        self.mrg_rr = False
        self.speaker = ''

    def to_str(self):
        def edit_str(rm, rr):
            if rm and rr: return 'RM,RR'
            elif rm: return 'RM'
            elif rr: return 'RR'
            else: return '-'

        dfl_feats = '|'.join((self.speaker, self.dps_tag, str(int(self.is_edit)),
                             edit_str(self.dps_rm, self.dps_rr),
                             edit_str(self.mrg_rm, self.mrg_rr)))
        props = (self.id, self.word, self.pos, self.pos,
                 dfl_feats, self.head, self.label)
        return '%d\t%s\t-\t%s\t%s\t%s\t%d\t%s\t-\t-' % props



class Sentence(object):
    def __init__(self, sent_str):
        self.tokens = [Token(line) for line in sent_str.split('\n')]

    def add_edits(self, edits):
        for token in self.tokens:
            if (token.id-1) in edits:
                token.is_edit = True
        self.mark_dps_edits()

    def add_dps(self, offset, dps):
        i = 0
        for token in self.tokens:
            if token.pos != '-DFL-':
                dps_w, dps_p, dps_tag, dps_edit, saw_ip, speaker = dps[i + offset]
                if token.word != dps_w:
                    assert token.word == dps_w
                i += 1
                token.speaker = speaker
                token.dps_tag = dps_tag
                token.dps_rm = dps_edit
                token.dps_rr = saw_ip
        return offset + i

    def mark_dps_edits(self):
        """Use the mrg dps edits, as the others refer to different sentence
        boundaries."""
        edit_depth = 0
        saw_ip = False
        for i, token in enumerate(self.tokens):
            if token.word == r'\[':
                edit_depth += 1
                saw_ip = False
            if edit_depth >= 1:
                token.mrg_rm = True
            if saw_ip:
                token.mrg_rr = True
            if token.word == r'\+':
                edit_depth -= 1
                saw_ip = True
            if token.word == r'\]':
                if not saw_ip:
                    # Assume prev token is actually repair, not reparandum
                    # This should only effect 3 cases
                    self.tokens[i - 1].dps_rm = False
                    if edit_depth >= 1:
                        edit_depth -= 1
                saw_ip = False

    def to_str(self):
        return '\n'.join(token.to_str() for token in self.tokens)

    def merge_mwe(self, mwe, parent_label=None, new_label=None):
        strings = mwe.split('_')
        assert len(strings) == 2
        for i, token in enumerate(self.tokens):
            if i == 0: continue
            prev = self.tokens[i - 1]
            if prev.word.lower() != strings[0] or token.word.lower() != strings[1]:
                continue
            if token.head == i:
                child = token
                head = prev
            elif prev.head == (i + 1):
                child = prev
                head = token
            elif prev.head == token.head:
                head = token
                child = prev
            else:
                raise StandardError, '\t'.join((prev.word, token.word, str(prev.head), str(token.head), str(i)))
            head.word = mwe
            head.pos = 'MWE' if (head.label != 'parataxis' and head.dps_tag == '-') else 'UH'
            child.word = '<erased>'
            if new_label is not None:
                head.label = new_label
        self.rm_tokens(lambda t: t.word == '<erased>')

    def rm_tokens(self, rejector):
        global uhs
        # 0 is root in conll format
        id_map = {0: 0}
        rejected = set()
        new_id = 1
        for token in self.tokens:
            id_map[token.id] = new_id
            if not rejector(token):
                new_id += 1
            else:
                rejected.add(token.id)
        for token in self.tokens:
            while token.head in rejected:
                head = self.tokens[token.head - 1]
                token.head = head.head
                token = head
        self.tokens = [token for token in self.tokens if not rejector(token)]
        n = len(self.tokens)
        for token in self.tokens:
            token.id = id_map[token.id]
            try:
                token.head = id_map[token.head]
            except:
                print >> sys.stderr, token.word
                raise
            if token.head > n:
                token.head = 0
            if token.head == token.id:
                token.head -= 1

    def lower_case(self):
        for token in self.tokens:
            token.word = token.word.lower()


def divide_files(swbd_loc):
    """Divide data into train/dev/test/dev2 split following Johnson and Charniak
    division"""
    swbd_loc = str(Path(swbd_loc).join('parsed').join('mrg').join('swbd'))
    train = []
    test = []
    dev = []
    dev2 = []
    files = []
    # pathlib's just a convenient path-handling library. os/os.path suck
    files.extend(str(f) for f in Path(swbd_loc).join('2'))
    files.extend(str(f) for f in Path(swbd_loc).join('3'))
    files.extend(str(f) for f in Path(swbd_loc).join('4'))
 
    for filename in files:
        if not filename.endswith('.mrg'): continue
        filenum = int(filename[-8:-4])
        if filenum < 4000:
            train.append(filename)
        elif 4000 < filenum <= 4154:
            test.append(filename)
        elif 4500 < filenum <= 4936:
            dev.append(filename)
        else:
            dev2.append(filename)
    return train, test, dev, dev2


def preprocess_mrg(mrg_str):
    lines = mrg_str.split('\n')
    lines = [l for l in lines if not l.startswith('( (CODE')]
    lines = [l for l in lines if not l.startswith('*x*')]
    return '\n'.join(lines)


def get_edited_yields(mrg_str):
    ptb_file = PTBFile(string=mrg_str, path='/tmp/tmp')
    edits = []
    for sent in ptb_file.children():
        under_edit = set([])
        words = [w for w in sent.listWords() if not w.isTrace()]
        word_id = dict((w.wordID, i) for i, w in enumerate(words))
        for node in sent.breadthList():
            if node.label != 'EDITED':
                continue
            for word in node.listWords():
                if not word.isTrace():
                    under_edit.add(word_id[word.wordID])
        edits.append(under_edit)
    return edits


def convert_to_conll(mrg_str, name):
    """Run the Stanford dependency converter over the mrg file, via the temp
    files /tmp/*.mrg and /tmp/*.dep"""
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


def do_section(locs, out_dir, name):
    out_dir = Path(out_dir)
    raw = out_dir.join('%s.raw_conll' % name).open('w')
    conll = out_dir.join('%s.conll' % name).open('w')
    pos = out_dir.join('%s.pos' % name).open('w')
    txt = out_dir.join('%s.txt' % name).open('w')
    for f in locs:
        mrg_txt = open(f).read()
        if f == Path(f).parts[-1] == 'sw2065.mrg':
            mrg_txt = fix_bracket_err(mrg_txt)
        mrg_txt = preprocess_mrg(mrg_txt)
        edits = get_edited_yields(mrg_txt)
        dep_txt = convert_to_conll(mrg_txt, Path(f).parts[-1])
        raw.write(dep_txt)
        # Now use sentence objects
        sents = [Sentence(s) for s in dep_txt.strip().split('\n\n')]
        dps_toks = _read_dps(_get_dps_loc(f))
        dep_txt = []
        assert len(sents) == len(edits)
        tok_id = 0
        for i, sent in enumerate(sents):
            sent.add_edits(edits[i])
            tok_id = sent.add_dps(tok_id, dps_toks)
            sent.rm_tokens(lambda token: token.pos == '-DFL-')
            sent.rm_tokens(lambda token: token.pos == 'XX')
            sent.rm_tokens(lambda token: token.word[-1] == '-')
            sent.rm_tokens(lambda token: token.pos in PUNCT)
            sent.rm_tokens(lambda token: token.word.lower() in UHS)
            sent.lower_case()
            sent.merge_mwe('you_know')
            sent.merge_mwe('i_mean')
            if len(sent.tokens) >= 2:
                dep_txt.append(sent.to_str())
        dep_txt = u'\n\n'.join(dep_txt)
        conll.write(dep_txt)
        pos.write(u'\n'.join(u' '.join('%s/%s' % (w.word, w.pos) for w in sent.tokens)
                             for sent in sents if len(sent.tokens) >= 2))
        txt.write(u'\n'.join(u' '.join(w.word for w in s.tokens) for s in sents
                             if len(sent.tokens) >= 3))
        conll.write(u'\n\n')
        pos.write(u'\n')
        txt.write(u'\n')


def _get_dps_loc(mrg_loc):
    mrg_loc = str(mrg_loc)
    return mrg_loc.replace('parsed/mrg/', 'dysfl/dps/').replace('.mrg', '.dps')


def _read_dps(dps_loc):
    header, text = re.split(r'===+', open(dps_loc).read())
    toks = {}
    tok_id = 0
    tag = '-'
    metadata = set(['E_S', 'N_S', '+', '[', ']'])
    edit_depth = 0
    saw_ip = False
    skip_next = False
    speaker = '??'
    for word in text.split():
        if not word.strip():
            continue
        if word.startswith('SpeakerA') or word.startswith('SpeakerB'):
            speaker = word.split('/')[0].replace('Speaker', '')
            skip_next = True
            continue
        elif skip_next:
            skip_next = False
            continue
        if word == '{F':
            tag = 'F'
        elif word == '{D':
            tag = 'D'
        elif word == '{C':
            tag = 'C'
        elif word == '{E':
            tag = 'E'
        elif word == '}':
            tag = '-'
        elif word == '[':
            edit_depth += 1
            saw_ip = False
        elif word == ']':
            if not saw_ip and edit_depth >= 1:
                edit_depth -= 1
            saw_ip = False
        elif word == '+':
            edit_depth -= 1
            saw_ip = True
        elif '/' in word:
            word, pos = word.rsplit('/', 1)
            toks[tok_id] = (word, pos, tag, edit_depth != 0, saw_ip, speaker)
            tok_id += 1
    return toks

 
def main(ptb_loc, out_dir):
    train, test, dev, dev2 = divide_files(ptb_loc)
    do_section(train, out_dir, 'train')
    do_section(test, out_dir, 'test')
    do_section(dev, out_dir, 'dev')
    do_section(dev2, out_dir, 'dev2')


if __name__ == '__main__':
    plac.call(main)
