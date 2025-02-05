import os
import torch
import numpy as np

from PIL import Image
from pycocotools.coco import COCO
from torch.utils.data import Dataset
from pycocotools import mask as maskUtils
from tqdm import tqdm

class COCODataset(Dataset):
    def __init__(self, root, train, transform=None):
        super().__init__()
        self.directory = "train2017" if train else "val2017"
        annotations = os.path.join(root, "annotations", f"instances_{self.directory}.json")
        
        self.coco = COCO(annotations)
        self.root = root
        self.transform = transform
        self.categories = self._get_categories()

        # category idx 순서대로 remapping
        self.new_categories = {}
        for i in range(len(self.categories)):
            self.new_categories[list(self.categories.values())[i]] = i

        if self.directory == 'train2017':
            self.id_list = list(np.load('./except_data_list/train_list.npy').astype(np.int32))
        elif self.directory == 'val2017':
            self.id_list = list(np.load('./except_data_list/val_list.npy').astype(np.int32))

    def _get_categories(self):
        categories = {0: "background"}
        for category in self.coco.cats.values():
            categories[category["id"]] = category["name"]
        return categories

    def _polygon_to_mask(self, segmentations, width, height):
        binary_mask = []
        for seg in segmentations:
            rles = maskUtils.frPyObjects([seg], height, width)
            binary_mask.append(maskUtils.decode(rles))

        combined_mask = np.sum(binary_mask, axis=0).squeeze()
        return combined_mask

    def __getitem__(self, index):
        se_id = int(self.id_list[index])
        file_name = self.coco.loadImgs(se_id)[0]["file_name"]
        image_path = os.path.join(self.root + self.directory + '/' + file_name)
        
        # load img
        image = Image.open(image_path).convert("RGB")
        width, height = image.size

        # load ann
        boxes = []
        masks = []
        labels = []
        anns = self.coco.loadAnns(self.coco.getAnnIds(se_id))
        
        for ann in anns:
            x, y, w, h = ann["bbox"]
            segmentations = ann["segmentation"]
            # try:
            #     mask = self._polygon_to_mask(segmentations, width, height) ## 동작 확인 필요, 확인 끝나면  try, except 제거
            # except:
            #     return se_id
            mask = self._polygon_to_mask(segmentations, width, height) ## 동작 확인 필요, 확인 끝나면  try, except 제거
            
            boxes.append([x, y, x + w, y + h])
            masks.append(mask)
            category_id = self.new_categories[self.categories[ann["category_id"]]] # category remapping
            labels.append(category_id)

        target = {"image_id": torch.LongTensor([se_id]),
                  "boxes": torch.FloatTensor(boxes),
                  "masks": torch.FloatTensor(masks),
                  "labels": torch.LongTensor(labels)
                 }
        # img, box augmentation (val의 경우 transform 다르게 설정)
        image, target = self.transform(image, target)
        
        return image, target

    def __len__(self):
        return len(self.id_list)
