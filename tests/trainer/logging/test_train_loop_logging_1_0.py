"""
Tests to ensure that the training loop works with a dict (1.0)
"""
from tests.base.boring_model import BoringModel, RandomDictDataset, RandomDictStringDataset
import os
import torch
import pytest

from pytorch_lightning import Trainer
from tests.base.deterministic_model import DeterministicModel


def test__training_step__log(tmpdir):
    """
    Tests that only training_step can be used
    """
    os.environ['PL_DEV_DEBUG'] = '1'

    class TestModel(DeterministicModel):
        def training_step(self, batch, batch_idx):
            acc = self.step(batch, batch_idx)
            acc = acc + batch_idx

            # -----------
            # default
            # -----------
            self.log('default', acc)

            # -----------
            # logger
            # -----------
            # on_step T on_epoch F
            self.log('l_s', acc, on_step=True, on_epoch=False, prog_bar=False, logger=True)

            # on_step F on_epoch T
            self.log('l_e', acc, on_step=False, on_epoch=True, prog_bar=False, logger=True)

            # on_step T on_epoch T
            self.log('l_se', acc, on_step=True, on_epoch=True, prog_bar=False, logger=True)

            # -----------
            # pbar
            # -----------
            # on_step T on_epoch F
            self.log('p_s', acc, on_step=True, on_epoch=False, prog_bar=True, logger=False)

            # on_step F on_epoch T
            self.log('p_e', acc, on_step=False, on_epoch=True, prog_bar=True, logger=False)

            # on_step T on_epoch T
            self.log('p_se', acc, on_step=True, on_epoch=True, prog_bar=True, logger=False)

            self.training_step_called = True
            return acc

        def backward(self, trainer, loss, optimizer, optimizer_idx):
            loss.backward()

    model = TestModel()
    model.val_dataloader = None

    trainer = Trainer(
        default_root_dir=tmpdir,
        limit_train_batches=2,
        limit_val_batches=2,
        max_epochs=2,
        log_every_n_steps=1,
        weights_summary=None,
    )
    trainer.fit(model)

    # make sure correct steps were called
    assert model.training_step_called
    assert not model.training_step_end_called
    assert not model.training_epoch_end_called

    # make sure all the metrics are available for callbacks
    logged_metrics = set(trainer.logged_metrics.keys())
    expected_logged_metrics = {
        'epoch',
        'default',
        'l_e',
        'l_s',
        'l_se',
        'step_l_se',
        'epoch_l_se',
    }
    assert logged_metrics == expected_logged_metrics

    pbar_metrics = set(trainer.progress_bar_metrics.keys())
    expected_pbar_metrics = {
        'p_e',
        'p_s',
        'p_se',
        'step_p_se',
        'epoch_p_se',
    }
    assert pbar_metrics == expected_pbar_metrics

    callback_metrics = set(trainer.callback_metrics.keys())
    callback_metrics.remove('debug_epoch')
    expected_callback_metrics = set()
    expected_callback_metrics = expected_callback_metrics.union(logged_metrics)
    expected_callback_metrics = expected_callback_metrics.union(pbar_metrics)
    expected_callback_metrics.remove('epoch')
    assert callback_metrics == expected_callback_metrics


def test__training_step__epoch_end__log(tmpdir):
    """
    Tests that only training_step can be used
    """
    os.environ['PL_DEV_DEBUG'] = '1'

    class TestModel(DeterministicModel):
        def training_step(self, batch, batch_idx):
            self.training_step_called = True
            acc = self.step(batch, batch_idx)
            acc = acc + batch_idx
            self.log('a', acc, on_step=True, on_epoch=True)
            self.log_dict({'a1': acc, 'a2': acc})
            return acc

        def training_epoch_end(self, outputs):
            self.training_epoch_end_called = True
            self.log('b1', outputs[0]['loss'])
            self.log('b', outputs[0]['loss'], on_epoch=True, prog_bar=True, logger=True)

        def backward(self, trainer, loss, optimizer, optimizer_idx):
            loss.backward()

    model = TestModel()
    model.val_dataloader = None

    trainer = Trainer(
        default_root_dir=tmpdir,
        limit_train_batches=2,
        limit_val_batches=2,
        max_epochs=2,
        log_every_n_steps=1,
        weights_summary=None,
    )
    trainer.fit(model)

    # make sure correct steps were called
    assert model.training_step_called
    assert not model.training_step_end_called
    assert model.training_epoch_end_called

    # make sure all the metrics are available for callbacks
    logged_metrics = set(trainer.logged_metrics.keys())
    expected_logged_metrics = {'epoch', 'a', 'step_a', 'epoch_a', 'b', 'b1', 'a1', 'a2'}
    assert logged_metrics == expected_logged_metrics

    pbar_metrics = set(trainer.progress_bar_metrics.keys())
    expected_pbar_metrics = {
        'b',
    }
    assert pbar_metrics == expected_pbar_metrics

    callback_metrics = set(trainer.callback_metrics.keys())
    callback_metrics.remove('debug_epoch')
    expected_callback_metrics = set()
    expected_callback_metrics = expected_callback_metrics.union(logged_metrics)
    expected_callback_metrics = expected_callback_metrics.union(pbar_metrics)
    expected_callback_metrics.remove('epoch')
    assert callback_metrics == expected_callback_metrics


@pytest.mark.parametrize(['batches', 'log_interval', 'max_epochs'], [(1, 1, 1), (64, 32, 2)])
def test__training_step__step_end__epoch_end__log(tmpdir, batches, log_interval, max_epochs):
    """
    Tests that only training_step can be used
    """
    os.environ['PL_DEV_DEBUG'] = '1'

    class TestModel(BoringModel):
        def training_step(self, batch, batch_idx):
            self.training_step_called = True
            loss = self.step(batch[0])
            self.log('a', loss, on_step=True, on_epoch=True)
            return loss

        def training_step_end(self, out):
            self.training_step_end_called = True
            self.log('b', out, on_step=True, on_epoch=True, prog_bar=True, logger=True)
            return out

        def training_epoch_end(self, outputs):
            self.training_epoch_end_called = True
            self.log('c', outputs[0]['loss'], on_epoch=True, prog_bar=True, logger=True)
            self.log('d/e/f', 2)

    model = TestModel()
    model.val_dataloader = None

    trainer = Trainer(
        default_root_dir=tmpdir,
        limit_train_batches=batches,
        limit_val_batches=batches,
        max_epochs=max_epochs,
        log_every_n_steps=log_interval,
        weights_summary=None,
    )
    trainer.fit(model)

    # make sure correct steps were called
    assert model.training_step_called
    assert model.training_step_end_called
    assert model.training_epoch_end_called

    # make sure all the metrics are available for callbacks
    logged_metrics = set(trainer.logged_metrics.keys())
    expected_logged_metrics = {
        'a', 'step_a', 'epoch_a',
        'b', 'step_b', 'epoch_b',
        'c',
        'd/e/f',
        'epoch'
    }
    assert logged_metrics == expected_logged_metrics

    pbar_metrics = set(trainer.progress_bar_metrics.keys())
    expected_pbar_metrics = {'b', 'c', 'epoch_b', 'step_b'}
    assert pbar_metrics == expected_pbar_metrics

    callback_metrics = set(trainer.callback_metrics.keys())
    callback_metrics.remove('debug_epoch')
    expected_callback_metrics = set()
    expected_callback_metrics = expected_callback_metrics.union(logged_metrics)
    expected_callback_metrics = expected_callback_metrics.union(pbar_metrics)
    expected_callback_metrics.remove('epoch')
    assert callback_metrics == expected_callback_metrics

    # assert the loggers received the expected number
    assert len(trainer.dev_debugger.logged_metrics) == ((batches / log_interval) * max_epochs) + max_epochs


@pytest.mark.parametrize(['batches', 'fx', 'result'], [(1, min, 0), (2, max, 1), (11, max, 10)])
def test__training_step__log_max_reduce_fx(tmpdir, batches, fx, result):
    """
    Tests that log works correctly with different tensor types
    """
    class TestModel(BoringModel):
        def training_step(self, batch, batch_idx):
            acc = self.step(batch[0])
            self.log('foo', torch.tensor(batch_idx).long(), on_step=False, on_epoch=True, reduce_fx=fx)
            return acc

        def validation_step(self, batch, batch_idx):
            output = self.layer(batch)
            loss = self.loss(batch, output)
            self.log('bar', torch.tensor(batch_idx).float(), on_step=False, on_epoch=True, reduce_fx=fx)
            return {"x": loss}

    model = TestModel()
    trainer = Trainer(
        default_root_dir=tmpdir,
        limit_train_batches=batches,
        limit_val_batches=batches,
        max_epochs=2,
        weights_summary=None,
    )
    trainer.fit(model)

    # make sure types are correct
    assert trainer.logged_metrics['foo'] == result
    assert trainer.logged_metrics['bar'] == result


def test_tbptt_log(tmpdir):
    """
    Tests that only training_step can be used
    """
    truncated_bptt_steps = 2
    sequence_size = 30
    batch_size = 30

    x_seq = torch.rand(batch_size, sequence_size, 1)
    y_seq_list = torch.rand(batch_size, sequence_size, 1).tolist()

    class MockSeq2SeqDataset(torch.utils.data.Dataset):
        def __getitem__(self, i):
            return x_seq, y_seq_list

        def __len__(self):
            return 1

    class TestModel(BoringModel):
        def __init__(self):
            super().__init__()
            self.test_hidden = None
            self.layer = torch.nn.Linear(2, 2)

        def training_step(self, batch, batch_idx, hiddens):
            try:
                assert hiddens == self.test_hidden, "Hidden state not persistent between tbptt steps"
            except Exception as e:
                print(e)

            self.test_hidden = torch.rand(1)

            x_tensor, y_list = batch
            assert x_tensor.shape[1] == truncated_bptt_steps, "tbptt split Tensor failed"

            y_tensor = torch.tensor(y_list, dtype=x_tensor.dtype)
            assert y_tensor.shape[1] == truncated_bptt_steps, "tbptt split list failed"

            pred = self(x_tensor.view(batch_size, truncated_bptt_steps))
            loss_val = torch.nn.functional.mse_loss(
                pred, y_tensor.view(batch_size, truncated_bptt_steps))

            self.log('a', loss_val, on_epoch=True)

            return {'loss': loss_val, 'hiddens': self.test_hidden}

        def on_train_epoch_start(self) -> None:
            self.test_hidden = None

        def train_dataloader(self):
            return torch.utils.data.DataLoader(
                dataset=MockSeq2SeqDataset(),
                batch_size=batch_size,
                shuffle=False,
                sampler=None,
            )

    model = TestModel()
    model.training_epoch_end = None
    model.example_input_array = torch.randn(5, truncated_bptt_steps)

    trainer = Trainer(
        default_root_dir=tmpdir,
        limit_train_batches=10,
        limit_val_batches=0,
        truncated_bptt_steps=truncated_bptt_steps,
        max_epochs=2,
        row_log_interval=2,
        weights_summary=None,
    )
    trainer.fit(model)

    generated = set(trainer.logged_metrics.keys())
    expected = {'a', 'step_a', 'epoch_a', 'epoch'}
    assert generated == expected


def test_different_batch_types_for_sizing(tmpdir):

    class TestModel(BoringModel):
        def training_step(self, batch, batch_idx):
            assert isinstance(batch, dict)
            a = batch['a']
            acc = self.step(a)
            self.log('a', {'d1': 2, 'd2': torch.tensor(1)}, on_step=True, on_epoch=True)
            return acc

        def validation_step(self, batch, batch_idx):
            assert isinstance(batch, dict)
            a = batch['a']
            output = self.layer(a)
            loss = self.loss(batch, output)
            self.log('n', {'d3': 2, 'd4': torch.tensor(1)}, on_step=True, on_epoch=True)
            return {"x": loss}

        def train_dataloader(self):
            return torch.utils.data.DataLoader(RandomDictDataset(32, 64), batch_size=32)

        def val_dataloader(self):
            return torch.utils.data.DataLoader(RandomDictDataset(32, 64), batch_size=32)

    model = TestModel()
    trainer = Trainer(
        default_root_dir=tmpdir,
        limit_train_batches=1,
        limit_val_batches=2,
        max_epochs=1,
        weights_summary=None,
    )
    trainer.fit(model)

    generated = set(trainer.logger_connector.logged_metrics)
    expected = {
        'epoch_a', 'a',
        'n', 'step_n/epoch_0', 'epoch_n',
        'epoch'
    }

    assert generated == expected


def test_validation_step_with_string_data_logging(tmpdir):

    class TestModel(BoringModel):
        def training_step(self, batch, batch_idx):
            output = self.layer(batch["x"])
            loss = self.loss(batch, output)
            return {"loss": loss}

        def validation_step(self, batch, batch_idx):
            output = self.layer(batch["x"])
            loss = self.loss(batch, output)
            self.log("x", loss)
            return {"x": loss}

    # fake data
    train_data = torch.utils.data.DataLoader(RandomDictStringDataset(32, 64))
    val_data = torch.utils.data.DataLoader(RandomDictStringDataset(32, 64))

    # model
    model = TestModel()
    trainer = Trainer(
        default_root_dir=tmpdir,
        limit_train_batches=1,
        limit_val_batches=1,
        max_epochs=1,
        weights_summary=None,
    )
    trainer.fit(model, train_data, val_data)
