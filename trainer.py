import copy
import time
import torch

from torch.optim import Adam
from torch.nn.modules import loss as nnloss
import torchvision.transforms as transforms
from torch.optim.lr_scheduler import ReduceLROnPlateau

from network import get_pretrained_iv3_transforms, SiameseNetwork
from utils import create_logger


logger = create_logger(__name__)


class QuasiSiameseNetwork(object):

    def __init__(self, args):
        input_size = (args.inputSize, args.inputSize)

        self.input_size = input_size
        self.lr = args.learningRate

        self.criterion = nnloss.MSELoss()

        self.transforms = {}

        self.model = SiameseNetwork()

        if torch.cuda.device_count() > 1:
            logger.info('Using {} GPUs'.format(torch.cuda.device_count()))
            self.model = nn.DataParallel(self.model)

        for s in ('train', 'validation', 'test'):
            self.transforms[s] = get_pretrained_iv3_transforms(s)

        logger.debug('Num params: {}'.format(
            len([_ for _ in self.model.parameters()])))

        self.optimizer = Adam(self.model.parameters(), lr=self.lr)
        self.lr_scheduler = ReduceLROnPlateau(self.optimizer,
                                              factor=0.1,
                                              patience=10,
                                              min_lr=1e-5,
                                              verbose=True)

    def run_epoch(self, epoch, loader, device, phase='train', accuracy_threshold=0.01):
        assert phase in ('train', 'validation', 'test')

        self.model = self.model.to(device)

        logger.info('Phase: {}, Epoch: {}'.format(phase, epoch))

        if phase == 'train':
            self.model.train()  # Set model to training mode
        else:
            self.model.eval()

        running_loss = 0.0
        running_corrects = 0
        running_n = 0.0

        for idx, (image1, image2, labels) in enumerate(loader):
            image1 = image1.to(device)
            image2 = image2.to(device)
            labels = labels.float().to(device)

            if phase == 'train':
                # zero the parameter gradients
                self.optimizer.zero_grad()

            with torch.set_grad_enabled(phase == 'train'):
                outputs = self.model(image1, image2).squeeze()
                loss = self.criterion(outputs, labels)

                if phase == 'train':
                    loss.backward()
                    self.optimizer.step()

            running_loss += loss.item() * image1.size(0)
            running_corrects += (outputs - labels.data).abs().le(accuracy_threshold).sum()
            running_n += image1.size(0)

            if idx % 1 == 0:
                logger.info('\tBatch {}: Loss: {:.4f} Acc: {:.4f}'.format(
                    idx, running_loss / running_n, running_corrects.double() / running_n))

        epoch_loss = running_loss / running_n
        epoch_acc = running_corrects.double() / running_n

        logger.info('{}: Loss: {:.4f}'.format(
            phase, epoch_loss))

        return epoch_loss, epoch_acc

    def train(self, n_epochs, datasets, device, save_path):
        train_set, train_loader = datasets.load('train')
        validation_set, validation_loader = datasets.load('validation')

        best_acc, best_model_wts = 0.0, copy.deepcopy(
            self.model.state_dict())

        start_time = time.time()
        for epoch in range(n_epochs):
            # train network
            train_loss, train_acc = self.run_epoch(
                epoch, train_loader, device, phase='train')

            # eval on validation
            validation_loss, validation_acc = self.run_epoch(
                epoch, validation_loader, device, phase='validation')

            self.lr_scheduler.step(validation_loss)

            if validation_acc > best_acc:
                best_acc = validation_acc
                best_model_wts = copy.deepcopy(self.model.state_dict())

                logger.info('Checkpoint: Saving to {}'.format(save_path))
                torch.save(best_model_wts, save_path)

        time_elapsed = time.time() - start_time
        logger.info('Training complete in {:.0f}m {:.0f}s'.format(
            time_elapsed // 60, time_elapsed % 60))

        logger.info('Best validation Accuracy: {:4f}.'.format(best_acc))

    def test(self, datasets, device, load_path):
        self.model.load_state_dict(torch.load(load_path))
        test_set, test_loader = datasets.load('test')
        self.run_epoch(0, test_loader, device, phase='test')
