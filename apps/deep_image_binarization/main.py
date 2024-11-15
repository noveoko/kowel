import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from PIL import Image
import numpy as np
import os

# Binarization Network
class BinarizationNet(nn.Module):
    def __init__(self):
        super(BinarizationNet, self).__init__()
        self.encoder = nn.Sequential(
            nn.Conv2d(1, 32, 3, padding=1),
            nn.ReLU(),
            nn.Conv2d(32, 64, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2, 2)
        )
        
        self.decoder = nn.Sequential(
            nn.ConvTranspose2d(64, 32, 2, stride=2),
            nn.ReLU(),
            nn.Conv2d(32, 1, 3, padding=1),
            nn.Sigmoid()
        )

    def forward(self, x):
        x = self.encoder(x)
        x = self.decoder(x)
        return x

# Custom Dataset
class BinarizationDataset(Dataset):
    def __init__(self, image_dir, transform=None):
        self.image_dir = image_dir
        self.transform = transform
        self.images = [f for f in os.listdir(image_dir) if f.endswith(('.png', '.jpg'))]

    def __len__(self):
        return len(self.images)

    def __getitem__(self, idx):
        img_path = os.path.join(self.image_dir, self.images[idx])
        image = Image.open(img_path).convert('L')
        
        if self.transform:
            image = self.transform(image)
            
        # Create ground truth by Otsu thresholding
        np_img = np.array(image)
        threshold = np.mean(np_img)
        binary = (np_img > threshold).astype(np.float32)
        return image, torch.FloatTensor(binary)

# Training function
def train_model(model, train_loader, num_epochs, device):
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters())
    
    for epoch in range(num_epochs):
        model.train()
        running_loss = 0.0
        
        for inputs, targets in train_loader:
            inputs, targets = inputs.to(device), targets.to(device)
            
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()
            
            running_loss += loss.item()
            
        print(f'Epoch {epoch+1}, Loss: {running_loss/len(train_loader):.4f}')

# Binarize function
def binarize_image(model, image_path, device):
    transform = transforms.Compose([
        transforms.Grayscale(),
        transforms.ToTensor()
    ])
    
    image = Image.open(image_path).convert('L')
    image = transform(image).unsqueeze(0).to(device)
    
    model.eval()
    with torch.no_grad():
        output = model(image)
        binary = (output > 0.5).float()
    
    return binary.cpu().squeeze().numpy()

# Main execution
def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # Initialize model
    model = BinarizationNet().to(device)
    
    # Setup dataset and dataloader
    transform = transforms.Compose([
        transforms.Resize((256, 256)),
        transforms.ToTensor()
    ])
    
    dataset = BinarizationDataset('path/to/images', transform=transform)
    train_loader = DataLoader(dataset, batch_size=32, shuffle=True)
    
    # Train model
    train_model(model, train_loader, num_epochs=10, device=device)
    
    # Save model
    torch.save(model.state_dict(), 'binarization_model.pth')

if __name__ == '__main__':
    main()
