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


@pytest.mark.parametrize('expected,actual,verdict',[('0.1900','0.1901','match'),('0.1900','0.1902','output'),('0.164','0.1648','match'),('0.19','0.164','output')])
def test_remaining_normative_precision_rows(expected,actual,verdict):
    assert examples.compare(expected,actual)==verdict


@pytest.mark.parametrize('expected,actual,verdict',[
 # Tibble/pillar column-type rows start with `<`; they are table headers, not bare inequality bounds.
 ('<chr>      <dbl>     <dbl>','  <chr>      <dbl>     <dbl>','match'),
 ('<dbl> <dbl> <dbl> <dbl> <int> <lgl>','  <dbl> <dbl> <dbl> <dbl> <int> <lgl>    ','match'),
 ('<chr> <dbl>','<chr> <int>','shape'),
 # Digits inside type metadata are not numeric output: no display-precision tolerance applies.
 ('<dbl[2]>','<dbl[3]>','shape'),('<chr [3]>','<chr [4]>','shape'),('<S3: foo2>','<S3: foo3>','shape'),
 ('<dbl[2]>','<dbl[2]>','match'),('<chr [3]>','  <chr [3]>  ','match'),
 # Bare numeric bounds remain unverifiable, even when identical.
 ('<2e-16','<2e-16','shape'),('>=0.05','>=0.05','shape'),('< 0.001','< 0.001','shape'),
])
def test_tibble_type_rows_are_not_bare_inequality_bounds(expected,actual,verdict):
    assert examples.compare(expected,actual)==verdict


@pytest.mark.parametrize('expected,actual,verdict',[
 ('[1] 100','[1] 101','output'),('[1] 0','[1] 1','output'),('n = 3','n = 4','output'),
 ('[1] 3','[1] 3.9','output'),('[1] 0','[1] -0','match'),('[1] 5','[1] +5','match'),
 ('[1] 999999','[1] 1000000','output'),('[1] 100','[1] 100','match'),
 ('[1] 1234568','[1] 1234567','match'),('[1] 1234568','[1] 1234570','output'),
 ('1e3','1001','match'),
])
def test_short_documented_integers_match_exactly(expected,actual,verdict):
    assert examples.compare(expected,actual)==verdict
