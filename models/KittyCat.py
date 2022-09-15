import torch
import torch.nn as nn
import numpy as np
import math
import random


class KittyCatConv(nn.Module):
    def __init__(self, d_k, device, h, l_k, seed):

        super(KittyCatConv, self).__init__()

        torch.manual_seed(seed)
        random.seed(seed)
        np.random.seed(seed)

        self.device = device
        self.d_k = d_k
        self.filter_length = [1, 3, 7, 9]

        self.proj_q = nn.Linear(d_k, 1, bias=False, device=device)
        self.proj_k = nn.Linear(d_k, 1, bias=False, device=device)

        self.conv_list_k = nn.ModuleList([
            nn.Conv1d(in_channels=h, out_channels=h, kernel_size=f, padding=int((f-1)/2))
            for f in self.filter_length]
        ).to(device)
        self.conv_list_q = nn.ModuleList([
            nn.Conv1d(in_channels=h, out_channels=h, kernel_size=f, padding=int((f-1)/2))
            for f in self.filter_length]
        ).to(device)

        self.proj_back_q = nn.Linear(1, self.d_k, bias=False).to(device)
        self.proj_back_k = nn.Linear(1, self.d_k, bias=False).to(device)

        self.norm_conv = nn.BatchNorm1d(h).to(device)
        self.activation = nn.ELU().to(device)

        for m in self.modules():
            if isinstance(m, nn.Conv1d):
                nn.init.kaiming_normal_(m.weight, mode='fan_in', nonlinearity='leaky_relu')

        self.factor = 1

    def forward(self, Q, K, V, attn_mask):

        b, h, l, d_k = Q.shape
        l_k = K.shape[2]
        Q_l = []
        K_l = []

        Q = self.proj_q(Q)
        K = self.proj_q(K)

        Q = Q.reshape(b, -1, l)
        K = K.reshape(b, -1, l_k)

        for i in range(len(self.filter_length)):

            Q_l.append(self.activation(self.norm_conv(self.conv_list_q[i](Q))))
            K_l.append(self.activation(self.norm_conv(self.conv_list_k[i](K))))

        Q_p = torch.cat(Q_l, dim=0).reshape(b, h, l * len(self.filter_length), -1)
        K_p = torch.cat(K_l, dim=0).reshape(b, h, l_k * len(self.filter_length), -1)

        Q = torch.topk(Q_p, l, dim=2)[0]
        Q = self.proj_back_q(Q)

        K_proj = K_p.reshape(b, h, len(self.filter_length), l_k)
        K = torch.mean(K_proj, dim=2)

        K, index = torch.topk(K, l_k, dim=-1)
        K = K.unsqueeze(-1)
        K = self.proj_back_k(K)

        #index = index.unsqueeze(-2).repeat(1, 1, l, 1)
        scores = torch.einsum('bhqd,bhkd->bhqk', Q, K) / np.sqrt(self.d_k)

        '''scores_f = torch.zeros(b, h, l, l_k, device=self.device)
        scores_f[torch.arange(b)[:, None, None, None],
                 torch.arange(h)[None, :, None, None],
                 torch.arange(l)[None, None, :, None], index] = scores'''

        attn = torch.softmax(scores, -1)
        context = torch.einsum('bhqk,bhkd->bhqd', attn, V)
        return context, attn