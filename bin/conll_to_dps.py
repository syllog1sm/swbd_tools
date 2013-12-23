"""Convert a CoNLL-format file into a .dps format file. The disfluency information
should be in the features field (column 5), which is | delimited. Subfields:
    1. F/D/E/C: Filler/Discourse/Explicit editing term/Conjunction
    2. Is the word under an EDITED node in mrg files?
    3. Is the word in disfluency annotation in the dps files?
    4. Is the word in disfluency annotation in the mrg files?
"""
import sys


class Token(object):
    def __init__(self, s):
        fields = s.strip().split()
        self.word = fields[1]
        self.pos = fields[3]
        if fields[5] == '-':
            feats = ('??', '-', '-', '-', '-')
        else:
            feats = fields[5].split('|')
        self.speaker = feats[0]
        self.dps_tag = feats[1]
        self.is_edit = feats[2] == '1'
        self.dps_rm = 'RM' in feats[3]
        self.dps_rr = 'RR' in feats[3]
        self.mrg_rm = 'RM' in feats[4]
        self.mrg_rr = 'RR' in feats[4]

print '*x* header *x*'
print
print '==============='
print
 
sent = []
open_rm = False
open_rr = False
open_tag = False
last_speaker = None
for line in sys.stdin:
    if not line.strip():
        print ' '.join(sent) + ' E_S'
        sent = []
        open_rm = False
        open_tag = False
        open_rr = False
        continue
    token = Token(line)
    if token.speaker != last_speaker:
        if last_speaker is not None:
            print
        print 'Speaker%s/SYM ./.' % token.speaker
        last_speaker = token.speaker
    if open_rm and not token.mrg_rm:
        sent.append('+')
        open_rm = False
        open_rr = True
    if token.dps_tag == '-' and open_tag:
        sent.append('}')
        open_tag = False
    if open_rr and not token.mrg_rr:
        sent.append(']')
        open_rr = False
    if token.dps_tag != '-':
        sent.append('{%s' % token.dps_tag) 
        open_tag = True
    # Use mrg tags
    if token.mrg_rm and not open_rm:
        sent.append('[')
        open_rm = True
    sent.append('%s/%s' % (token.word, token.pos))
