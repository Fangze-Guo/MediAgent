import torch
from torch import nn
import  pickle
from nnunet.training.model_restore import load_model_and_checkpoint_files
import os
import numpy as np
 
if __name__ == "__main__":
 
    #convert .model to .onnx
    Model_path = "/home/wzt/src/nnunet_projects/nnUNet_trained_models/nnUNet/3d_fullres/Task088_TumorSeg/nnUNetTrainerV2__nnUNetPlansv2.1"
    folds='all'
    checkpoint_name = "model_final_checkpoint" 
 
    trainer, params = load_model_and_checkpoint_files(Model_path, folds=folds, mixed_precision=True, checkpoint_name=checkpoint_name)  
    net = trainer.network
   
    checkpoint = torch.load(os.path.join( Model_path , folds, checkpoint_name +".model"))
 
    net.load_state_dict(checkpoint['state_dict'])
    net.eval()
    #(1,1,10,20,30)是我i任意写的，你要按照自己的输入数组维度更换
    dummy_input = torch.randn(1, 1, 112, 160, 128).to("cuda")
    torch.onnx.export(
        net,
        dummy_input,
        'dynamic-1.onnx',
        input_names=['input'],
        output_names=['output'],
        dynamic_axes = {'input': {0: 'batch_size'},'output': {0: 'batch_size'}}
        )