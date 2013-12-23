import plac

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
        fields = props[5].split('|')
        self.speaker = fields[0]
        self.dps_tag = fields[1]
        self.is_edit = fields[2] == '1'
        self.dps_rm = 'RM' in fields[3]
        self.dps_rr = 'RR' in fields[3]
        self.mrg_rm = 'RM' in fields[4]
        self.mrg_rr = 'RR' in fields[4]

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


def main(in_loc):
    sents = [Sentence(s) for s in open(in_loc).read().strip().split('\n\n')]
    for sent in sents:
        sent.rm_tokens(lambda t: t.is_edit)
        print '\n'.join(token.to_str() for token in sent.tokens)
        print


if __name__ == '__main__':
    plac.call(main)
