"""Add word timing information to a CoNLL-formatted dependencies file.
Timings are sourced from the Nite XML standoff annotations."""

import xml.etree.cElementTree as etree
import os.path
import os
import plac


class Token(object):
    def __init__(self, node):
        id_ = node.get('{http://nite.sourceforge.net/}id')
        self.sent_id = int(id_[1:].split('_')[0])
        self.word_id = int(id_.split('_')[1])
        self.id = id_
        self.start = node.get('{http://nite.sourceforge.net/}start')
        self.end = node.get('{http://nite.sourceforge.net/}end')
        self.pos = node.get('pos')
        self.orth = node.get('orth')
        self.pause = None
        self.is_partial = self.pos == 'XX' or self.orth.endswith('-')

    def __str__(self):
        return '%s\t%s\t%s\t%s' % (self.orth.lower(), self.pos, self.start, self.end)

    def __cmp__(self, other):
        return cmp((self.sent_id, self.word_id), (other.sent_id, other.word_id))


class Sentence(object):
    def __init__(self, filename, node):
        self.filename = filename
        self.id = int(node.get('{http://nite.sourceforge.net/}id')[1:])
        self.terminals = []
        for terminal in node.iter('{http://nite.sourceforge.net/}child'):
            self.terminals.append(terminal.get('href').split('#')[1][3:-1])

    def __cmp__(self, other):
        return cmp(self.id, other.id)


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
    for node in list(tree.iter('punc')) + list(tree.iter('sil')) + list(tree.iter('trace')):
        id_ = node.get('{http://nite.sourceforge.net/}id')
        tokens[id_] = None

    return tokens

def read_syntax(loc):
    tree = etree.parse(open(loc))
    sents = []
    for node in tree.iter('parse'):
        sents.append(Sentence(loc, node))
    return sents


def do_file(terms_a, terms_b, syntax_a, syntax_b):
    tokens = read_tokens(terms_a)
    tokens.update(read_tokens(terms_b))
    sentences = read_syntax(syntax_a) + read_syntax(syntax_b)
    lines = []
    for sent in sorted(sentences):
        for t in sent.terminals:
            #if t not in tokens:
            #    lines.append(str(sent.filename) + t)
            if t in tokens and tokens[t] and not tokens[t].is_partial:
                lines.append(str(tokens[t]))
        lines.append('')
    return lines


def split_files(terminals_dir, syntax_dir):
    def get_locs(filenum, terminals_dir, syntax_dir):
        term_a = 'sw%d.A.terminals.xml' % filenum
        term_b = 'sw%d.B.terminals.xml' % filenum
        syn_a = 'sw%d.A.syntax.xml' % filenum
        syn_b = 'sw%d.B.syntax.xml' % filenum
        return (os.path.join(terminals_dir, term_a),
                os.path.join(terminals_dir, term_b),
                os.path.join(syntax_dir, syn_a),
                os.path.join(syntax_dir, syn_b)
            )

    train = []
    dev = []
    dev2 = []
    test = []
    for filename in os.listdir(syntax_dir):
        if filename == 'CVS': continue
        filenum, speaker, _ = filename.split('.', 2)
        if speaker != 'A':
            continue
        filenum = int(filenum[2:])
        locs = get_locs(filenum, terminals_dir, syntax_dir)
        if filenum < 4000:
            train.append(locs)
        elif 4000 < filenum <= 4154:
            test.append(locs)
        elif 4500 < filenum <= 4936:
            dev.append(locs)
        else:
            dev2.append(locs)
    return train, dev, dev2, test


def main(terms_dir, syntax_dir, out_dir):
    train, dev, dev2, test = split_files(terms_dir, syntax_dir)
    for name, files in [('train', train), ('dev', dev), ('dev2', dev2), ('test', test)]:
        with open(os.path.join(out_dir, name), 'w') as out_file:
            lines = []
            for terms_a, terms_b, syntax_a, syntax_b in files:
                lines.extend(do_file(terms_a, terms_b, syntax_a, syntax_b))
                lines.append('')
            out_file.write('\n'.join(lines))


if __name__ == '__main__':
    plac.call(main)
