"""Add word timing information to a CoNLL-formatted dependencies file.
Timings are sourced from the Nite XML standoff annotations."""

import xml.etree.cElementTree as etree
import plac
import Treebank.PTB

class Token(object):
    def __init__(self, node):
        self.id = node.get('{http://nite.sourceforge.net/}id')
        self.start = node.get('{http://nite.sourceforge.net/}start')
        self.end = node.get('{http://nite.sourceforge.net/}end')
        self.pos = node.get('pos')
        self.orth = node.get('orth')
        self.pause = None

    def __str__(self):
        return '%s\t%s\t%s\t%s\t%s' % (self.id, self.orth, self.pos, self.start, self.end)


class Sentence(object):
    def __init__(self, node):
        self.id = node.get('{http://nite.sourceforge.net/}id')
        self.terminals = []
        for terminal in node.iter('{http://nite.sourceforge.net/}child'):
            self.terminals.append(terminal.get('href').split('#')[1][3:-1])


def read_tokens(loc):
    tree = etree.parse(open(loc))
    tokens = {} 
    last_token = None
    for node in tree.iter('word'):
        token = Token(node)
        tokens[token.id] = token
        if last_token is not None:
            if token.start in ('n/a', 'non-aligned') or last_token.end in ('n/a', 'non-aligned'):
                last_token.pause = 0.0
            else:
                last_token.pause = float(token.start) - float(last_token.end)
        last_token = token
    return tokens

def read_syntax(loc):
    tree = etree.parse(open(loc))
    sents = []
    for node in tree.iter('parse'):
        sents.append(Sentence(node))
    return sents

def get_ptb_sents(loc, side='A'):
    ptb_file = Treebank.PTB.PTBFile(path=loc)
    speaker = None
    bad_pos = set(['-DFL-', 'E_S', 'N_S'])
    for sent in ptb_file.children():
        if sent.getWord(0) is None:
            continue
        if sent.getWord(0).text.startswith('Speaker'):
            speaker = sent.getWord(0).text.replace('Speaker', '')[0]
            continue
        tokens = [t for t in sent.listWords()
                  if not t.isTrace() and not t.isPunct() and t.label not in bad_pos]
        if tokens and speaker == side:
            yield tokens


def main(terms_loc, syntax_loc, ptb_loc):
    tokens = read_tokens(terms_loc)
    sentences = read_syntax(syntax_loc)
    ptb_sents = list(get_ptb_sents(ptb_loc))
    sentences = [s for s in sentences if any(t in tokens for t in s.terminals)]
    print len(sentences), len(ptb_sents)
    for i, sent in enumerate(sentences):
        print ' '.join(w.text for w in ptb_sents[i])
        print '\n'.join(str(tokens[t]) for t in sent.terminals if t in tokens)
        print


if __name__ == '__main__':
    plac.call(main)
