#import <UIKit/UIKit.h>
#include "ios_compact_device.h"
extern void UIKit_GL_RestoreCurrentContext(void);
#import <CoreFoundation/CoreFoundation.h>
#import <CoreText/CoreText.h>

int supertux_ios_is_tablet(void)
{
    return UI_USER_INTERFACE_IDIOM() == UIUserInterfaceIdiomPad;
}

void supertux_ios_pump_run_loop(void)
{
    CFRunLoopRunInMode(kCFRunLoopDefaultMode, 0.25, true);
}

int supertux_ios_is_active(void)
{
    return [UIApplication sharedApplication].applicationState == UIApplicationStateActive;
}

int supertux_ios_compact_phone(void)
{
    const CGSize size = [UIScreen mainScreen].bounds.size;
    return supertux_compact_dimensions(UI_USER_INTERFACE_IDIOM() == UIUserInterfaceIdiomPad, size.width, size.height);
}

static UILabel *supertuxLoadingLabel = nil;
void supertux_ios_show_loading(void)
{
    if (supertuxLoadingLabel) return;
    UIWindow *window = [UIApplication sharedApplication].keyWindow;
    UIView *parent = window.rootViewController.view;
    if (!parent) return;
    supertuxLoadingLabel = [[UILabel alloc] initWithFrame:parent.bounds];
    supertuxLoadingLabel.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    supertuxLoadingLabel.backgroundColor = [UIColor blackColor];
    supertuxLoadingLabel.textColor = [UIColor whiteColor];
    supertuxLoadingLabel.textAlignment = NSTextAlignmentCenter;
    NSString *path = [[[NSBundle mainBundle] resourcePath] stringByAppendingPathComponent:@"data/fonts/SuperTux-Medium.ttf"];
    NSURL *url = [NSURL fileURLWithPath:path];
    CTFontManagerRegisterFontsForURL((CFURLRef)url, kCTFontManagerScopeProcess, NULL);
    CGDataProviderRef provider = CGDataProviderCreateWithFilename([path fileSystemRepresentation]);
    CGFontRef gameFont = provider ? CGFontCreateWithDataProvider(provider) : NULL;
    NSString *fontName = gameFont ? (NSString *)CGFontCopyPostScriptName(gameFont) : nil;
    UIFont *font = fontName ? [UIFont fontWithName:fontName size:24] : nil;
    supertuxLoadingLabel.font = font ? font : [UIFont boldSystemFontOfSize:24];
    [fontName release];
    if (gameFont) CGFontRelease(gameFont);
    if (provider) CGDataProviderRelease(provider);
    supertuxLoadingLabel.text = @"Loading...";
    [parent addSubview:supertuxLoadingLabel];
    CFRunLoopRunInMode(kCFRunLoopDefaultMode, 0.01, true);
    UIKit_GL_RestoreCurrentContext();
}
void supertux_ios_hide_loading(void)
{
    [supertuxLoadingLabel removeFromSuperview];
    [supertuxLoadingLabel release];
    supertuxLoadingLabel = nil;
}
