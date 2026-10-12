import pytest
from lib import _docexamples as examples


@pytest.mark.parametrize('expected,actual,verdict',[
 ('0.19','0.20','match'),('0.19','0.20001','output'),
 ('1e-04','2e-04','match'),('1.00e-04','1.02e-04','output'),
 ('-0.19','-0.20','match'),('55%','36 %','output'),('55%','0.55','shape'),
 ('1,234','1234','shape'),('NA','NaN','output'),('Inf','-Inf','output'),
 ('label [1] 1','other [1] 1','shape'),('[1] 1 2','[1] 1','shape'),
])
def test_documented_precision_cases(expected,actual,verdict):
    assert examples.compare(expected,actual)==verdict


@pytest.mark.parametrize('expected,actual,verdict',[
 ('p < 0.001','p = 0.001','output'),('p <= 0.001','p = 0.001','match'),
 ('p < 0.001','p < 2e-16','match'),('p < 0.001','p < 0.01','unverified'),
 ('p < 0.001','p > 0.01','unverified'),('p < 0.001','<2e-16','shape'),
 ('<2e-16','<2e-16','shape'),('p < 0.001','p < .','shape'),
])
def test_labeled_inequality_cases(expected,actual,verdict):
    assert examples.compare(expected,actual)==verdict
