import os
import yaml
import numpy as np
import tqdm
import torch
from torch import nn
import sys
sys.path.insert(0,'./')
from guided_diffusion.models import Model
import random
from ddim_inversion_utils import *
from utils import *
import devicetorch
device = devicetorch.get(torch)

with open('configs/blind_non_uniform_deblurring.yml', 'r') as f:
    task_config = yaml.safe_load(f)


### Reproducibility
torch.set_printoptions(sci_mode=False)
ensure_reproducibility(task_config['seed'])


with open( "data/celeba_hq.yml", "r") as f:
    config1 = yaml.safe_load(f)
config = dict2namespace(config1)
model, device = load_pretrained_diffusion_model(config)

### Define the DDIM scheduler
ddim_scheduler=DDIMScheduler(beta_start=config.diffusion.beta_start, beta_end=config.diffusion.beta_end, beta_schedule=config.diffusion.beta_schedule)
ddim_scheduler.set_timesteps(config.diffusion.num_diffusion_timesteps // task_config['delta_t'])#task_config['Denoising_steps']


img_np = (np.array(Image.open('data/motion_blur/00870_input.png')) / 255.)*2. - 1.
img_pil = Image.open('data/motion_blur/00870_gt.png')
img_torch = torch.tensor(img_np).permute(2, 0, 1).unsqueeze(0).float()
radii =  torch.ones([1, 1, 1]).to(device) * (np.sqrt(config.data.image_size*config.data.image_size*config.model.in_channels))

latent = torch.nn.parameter.Parameter(torch.randn( 1, config.model.in_channels, config.data.image_size, config.data.image_size).to(device))  
l2_loss=nn.MSELoss() #nn.L1Loss()
optimizer = torch.optim.Adam([{'params':latent,'lr':task_config['lr']}])#


for iteration in range(task_config['Optimization_steps']):
    optimizer.zero_grad()
    x_0_hat = DDIM_efficient_feed_forward(latent, model, ddim_scheduler)    
    loss = l2_loss(x_0_hat, img_torch.to(device))
    loss.backward()  
    optimizer.step()  

    #Project to the Sphere of radius sqrt(D)
    for param in latent:
        param.data.div_((param.pow(2).sum(tuple(range(0, param.ndim)), keepdim=True) + 1e-9).sqrt())
        param.data.mul_(radii)

    if iteration % 10 == 0:
        #psnr = psnr_orig(np.array(img_pil).astype(np.float32), process(x_0_hat, 0))
        #print(iteration, 'loss:', loss.item(), torch.norm(latent.detach()), psnr)
        Image.fromarray(np.concatenate([ process(img_torch.to(device), 0), process(x_0_hat, 0), np.array(img_pil).astype(np.uint8)], 1)).save('results/non_uniform_deblurring.png')

   


