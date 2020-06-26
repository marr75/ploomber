from pathlib import Path

import pytest
import jupytext
import nbformat

from ploomber import DAG, DAGConfigurator
from ploomber.tasks import NotebookRunner
from ploomber.products import File
from ploomber.exceptions import DAGBuildError
from ploomber.tasks import notebook


def test_can_execute_from_ipynb(path_to_assets, tmp_directory):
    dag = DAG()

    NotebookRunner(path_to_assets / 'sample.ipynb',
                   product=File(Path(tmp_directory, 'out.ipynb')),
                   dag=dag,
                   name='nb')
    dag.build()


def test_can_execute_to_html(path_to_assets, tmp_directory):
    dag = DAG()

    NotebookRunner(path_to_assets / 'sample.ipynb',
                   product=File(Path(tmp_directory, 'out.html')),
                   dag=dag,
                   name='nb')
    dag.build()


def test_can_execute_from_py(path_to_assets, tmp_directory):
    dag = DAG()

    NotebookRunner(path_to_assets / 'sample.py',
                   product=File(Path(tmp_directory, 'out.ipynb')),
                   dag=dag,
                   kernelspec_name='python3',
                   name='nb')
    dag.build()


def test_can_execute_with_parameters(tmp_directory):
    dag = DAG()

    code = """
    1 + 1
    """

    NotebookRunner(code,
                   product=File(Path(tmp_directory, 'out.ipynb')),
                   dag=dag,
                   kernelspec_name='python3',
                   params={'var': 1},
                   ext_in='py',
                   name='nb')
    dag.build()


def test_can_execute_when_product_is_metaproduct(tmp_directory):
    dag = DAG()

    code = """

from pathlib import Path

Path(product['model']).touch()
    """

    product = {'nb': File(Path(tmp_directory, 'out.ipynb')),
               'model': File(Path(tmp_directory, 'model.pkl'))}

    NotebookRunner(code,
                   product=product,
                   dag=dag,
                   kernelspec_name='python3',
                   params={'var': 1},
                   ext_in='py',
                   nb_product_key='nb',
                   name='nb')
    dag.build()


def test_raises_error_if_key_does_not_exist_in_metaproduct(tmp_directory):
    dag = DAG()

    product = {'some_notebook': File(Path(tmp_directory, 'out.ipynb')),
               'model': File(Path(tmp_directory, 'model.pkl'))}

    with pytest.raises(KeyError) as excinfo:
        NotebookRunner('',
                       product=product,
                       dag=dag,
                       kernelspec_name='python3',
                       params={'var': 1},
                       ext_in='py',
                       nb_product_key='nb',
                       name='nb')

    assert 'Key "nb" does not exist in product' in str(excinfo.value)


def test_failing_notebook_saves_partial_result(tmp_directory):
    dag = DAG()

    code = """
    raise Exception('failing notebook')
    """

    # attempting to generate an HTML report
    NotebookRunner(code,
                   product=File('out.html'),
                   dag=dag,
                   kernelspec_name='python3',
                   params={'var': 1},
                   ext_in='py',
                   name='nb')

    # build breaks due to the exception
    with pytest.raises(DAGBuildError):
        dag.build()

    # but the file with ipynb extension exists to help debugging
    assert Path('out.ipynb').exists()


def test_error_if_wrong_exporter_name(path_to_assets, tmp_directory):
    dag = DAG()

    with pytest.raises(ValueError) as excinfo:
        NotebookRunner(path_to_assets / 'sample.ipynb',
                       product=File(Path(tmp_directory, 'out.ipynb')),
                       dag=dag,
                       nbconvert_exporter_name='wrong_name')

    assert 'Unknown exporter "wrong_name"' in str(excinfo.value)


def test_error_if_cant_determine_exporter_name(path_to_assets, tmp_directory):
    dag = DAG()

    with pytest.raises(ValueError) as excinfo:
        NotebookRunner(path_to_assets / 'sample.ipynb',
                       product=File(Path(tmp_directory, 'out.wrong_ext')),
                       dag=dag,
                       nbconvert_exporter_name=None)

    assert 'Could not determine nbconvert exporter' in str(excinfo.value)


# TODO: we are not testing output, we have to make sure params are inserted
# correctly

def test_develop_saves_changes(tmp_directory, monkeypatch):
    dag = DAG()

    code = """
    1 + 1
    """
    p = Path('some_notebook.py')

    p.write_text(code)

    t = NotebookRunner(p,
                       product=File(Path(tmp_directory, 'out.ipynb')),
                       dag=dag,
                       kernelspec_name='python3',
                       params={'var': 1},
                       name='nb')

    def mock_jupyter_notebook(tmp):
        nb = jupytext.reads('2 + 2', fmt='py')
        nbformat.write(nb, tmp)

    dag.render()

    monkeypatch.setattr(notebook, '_open_jupyter_notebook',
                        mock_jupyter_notebook)
    monkeypatch.setattr(notebook, '_save',
                        lambda: True)

    t.develop()

    assert Path(p).read_text().strip() == '2 + 2'


def test_develop_workflow_with_hot_reload(tmp_directory, monkeypatch):
    cfg = DAGConfigurator()
    cfg.params.hot_reload = True
    dag = cfg.create()

    code = """
    1 + 1
    """
    p = Path('some_notebook.py')

    p.write_text(code)

    t = NotebookRunner(p,
                       product=File(Path(tmp_directory, 'out.ipynb')),
                       dag=dag,
                       kernelspec_name='python3',
                       params={'var': 1},
                       name='nb')

    def mock_jupyter_notebook(tmp):
        nb = jupytext.reads('2 + 2', fmt='py')
        nbformat.write(nb, tmp)

    dag.render()

    monkeypatch.setattr(notebook, '_open_jupyter_notebook',
                        mock_jupyter_notebook)
    monkeypatch.setattr(notebook, '_save',
                        lambda: True)

    t.develop()

    # source code must be updated
    assert str(t.source).strip() == '2 + 2'

    nb = nbformat.reads(t.source.rendered_nb_str, as_version=nbformat.NO_CONVERT)
    source = jupytext.writes(nb, fmt='py')

    assert '2 + 2' in source


# TODO: make a more general text and parametrize by all task types
# but we also have to test it at the source level
# also test at the DAG level, we have to make sure the property that
# code differ uses (raw code) it also hot_loaded
def test_hot_reload(tmp_directory):
    cfg = DAGConfigurator()
    cfg.params.hot_reload = True

    dag = cfg.create()

    path = Path('nb.py')
    path.write_text("""
1 + 1
    """)

    t = NotebookRunner(path,
                       product=File('out.html'),
                       dag=dag,
                       kernelspec_name='python3')

    t.render()

    path.write_text("""
2 + 2
    """)

    t.render()

    assert '2 + 2' in str(t.source)
    assert t.product._outdated_code_dependency()
    assert not t.product._outdated_data_dependencies()

    assert '2 + 2' in t.source.rendered_nb_str

    report = dag.build()

    assert report['Ran?'] == [True]

    # TODO: check task is not marked as outdated
